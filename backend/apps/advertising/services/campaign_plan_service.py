import logging

from django.utils import timezone

from apps.core.models import UserProfile
from apps.advertising.models import AdCampaignPlan, AdvertisingAccount, AdAgentDecision, AdCampaignBriefing
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.services.campaign_service import CampaignService
from apps.advertising.services.metrics_service import MetricsService
from apps.advertising.services.ai_copy_service import generate_ad_copy_with_fallback

logger = logging.getLogger('apps')

DEFAULT_CONVERSIONS_TRACKED = ['qualified_lead', 'reservation', 'sale']


class CampaignPlanService:
    """
    Camada "propor → aprovar → executar" para criação de campanha via chat
    (pedido do usuário: "Crie uma campanha para esta ninhada" nunca deve criar
    nada de fato — só depois de aprovação explícita). Reaproveita exatamente o
    mesmo CampaignService.create_campaign/add_negative_keywords já usados pelo
    fluxo manual (PromoteCampaignModal) — este service só orquestra o
    propor/aprovar em cima dele, nunca duplica a lógica de criação.
    """

    def propose(self, *, organization, litter, data: dict, justification: str = '') -> AdCampaignPlan:
        ad_groups = data.get('ad_groups') or []
        headlines = data.get('headlines') or []
        descriptions = data.get('descriptions') or []
        keywords = data.get('keywords') or []

        # Geração de copy por IA só entra no fluxo legado (1 ad group) — quando o agente já monta
        # ad_groups estruturados (múltiplos grupos, keywords com match type, RSAs por grupo), ele
        # mesmo é responsável pelo texto de cada grupo, não faz sentido gerar um resumo genérico
        # por cima.
        if litter and not ad_groups and not (headlines and descriptions):
            user_profile = UserProfile.objects.filter(organization=organization).first()
            openai_api_key = getattr(getattr(organization, 'agent_config', None), 'openai_api_key', '') or ''
            generated = generate_ad_copy_with_fallback(
                litter=litter, user_profile=user_profile,
                audience_description=data.get('audience_description', ''), openai_api_key=openai_api_key,
            )
            headlines = headlines or generated['ad_headlines']
            descriptions = descriptions or generated['ad_descriptions']
            keywords = keywords or generated['ad_keywords']

        if ad_groups:
            # Resumo agregado nos campos legados — mesma lógica de CampaignService.create_campaign,
            # só para exibição/compatibilidade (a estrutura real fica em ad_groups).
            headlines = [h for ag in ad_groups for ad in ag.get('ads', []) for h in ad['headlines']]
            descriptions = [d for ag in ad_groups for ad in ag.get('ads', []) for d in ad['descriptions']]
            keywords = [
                kw if isinstance(kw, str) else kw.get('text', '')
                for ag in ad_groups for kw in ag.get('keywords', [])
            ]

        return AdCampaignPlan.objects.create(
            organization=organization,
            litter=litter,
            name=data.get('name') or (f'Ninhada {litter.name}' if litter else 'Campanha Google Ads'),
            daily_budget=data['daily_budget'],
            region=data.get('region', ''),
            radius_km=data.get('radius_km'),
            bid_strategy=data.get('bid_strategy', 'manual_cpc'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            landing_url=data.get('landing_url', ''),
            ad_groups=ad_groups,
            headlines=headlines,
            descriptions=descriptions,
            keywords=keywords,
            negative_keywords=data.get('negative_keywords', []),
            conversions_tracked=data.get('conversions_tracked') or DEFAULT_CONVERSIONS_TRACKED,
            tracking_notes=data.get(
                'tracking_notes',
                'Atribuição automática via gclid/gbraid/wbraid + ValueTrack; conversões '
                'QUALIFIED/RESERVED/SOLD disparadas pelo CRM quando o lead avançar no funil.',
            ),
            justification=justification,
        )

    def reject(self, *, organization, plan_id) -> AdCampaignPlan:
        plan = AdCampaignPlan.objects.get(organization=organization, id=plan_id)
        if plan.status == 'proposed':
            plan.status = 'rejected'
            plan.decided_at = timezone.now()
            plan.save(update_fields=['status', 'decided_at'])
        return plan

    def execute(self, *, organization, plan_id):
        plan = AdCampaignPlan.objects.get(organization=organization, id=plan_id)
        if plan.status == 'executed':
            return plan.resulting_campaign
        if plan.status == 'rejected':
            raise GoogleAdsProviderError('Este plano já foi rejeitado — proponha um novo.', code='plan_rejected')

        account = AdvertisingAccount.objects.filter(organization=organization, is_active=True).first()
        if not account:
            raise GoogleAdsProviderError(
                'Nenhuma conta de anúncios conectada. Conecte uma conta Google Ads primeiro.',
                code='no_account',
            )

        campaign = CampaignService().create_campaign(
            organization=organization,
            advertising_account=account,
            litter=plan.litter,
            data={
                'name': plan.name,
                'daily_budget': float(plan.daily_budget),
                'region': plan.region,
                'radius_km': plan.radius_km,
                'start_date': plan.start_date,
                'end_date': plan.end_date,
                'landing_url': plan.landing_url,
                'ad_groups': plan.ad_groups,
                'ad_headlines': plan.headlines,
                'ad_descriptions': plan.descriptions,
                'ad_keywords': plan.keywords,
                # Vai direto no CampaignSpec da criação (agrupado por match type lá dentro) — mais
                # fiel que o follow-up separado de antes, que só suportava um match type por vez
                # para o lote inteiro.
                'negative_keywords': plan.negative_keywords,
                'geo_target_type': 'PRESENCE',
            },
            # Idempotência: se execute() for chamado de novo para o mesmo plano
            # (ex.: reenvio do tool call), não cria uma segunda campanha.
            client_request_id=f'plan-{plan.id}',
        )

        if plan.litter_id:
            AdCampaignBriefing.objects.update_or_create(
                campaign=campaign,
                defaults={
                    'product_description': f'Filhotes — {plan.litter.name}' if plan.litter else '',
                    'objective': plan.justification,
                    'primary_conversion': ', '.join(plan.conversions_tracked) if plan.conversions_tracked else '',
                    'negative_keywords': [
                        kw if isinstance(kw, str) else kw.get('text', '') for kw in plan.negative_keywords
                    ],
                    'notes': plan.tracking_notes,
                },
            )

        plan.status = 'executed'
        plan.resulting_campaign = campaign
        plan.decided_at = timezone.now()
        plan.save(update_fields=['status', 'resulting_campaign', 'decided_at'])

        # Snapshot no momento da criação = baseline (tudo zero/quase zero) — permite comparar
        # "como a campanha evoluiu desde que foi criada" mais tarde via evaluate_decision, em vez
        # de deixar metrics_snapshot vazio (o que forçaria o agente a inventar ou recusar comparar).
        snapshot = MetricsService().build_snapshot(campaign)
        AdAgentDecision.objects.create(
            organization=organization,
            campaign=campaign,
            action='execute_campaign_plan',
            before={},
            after={'plan_id': plan.id, 'external_campaign_id': campaign.external_campaign_id, 'status': campaign.status},
            reason=f'Plano de campanha #{plan.id} aprovado explicitamente pelo usuário no chat.',
            hypothesis=plan.justification,
            performed_by='agent',
            approval_status='confirmed_by_user',
            metrics_snapshot=snapshot,
        )
        return campaign
