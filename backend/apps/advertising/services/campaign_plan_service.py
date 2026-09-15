import logging

from django.utils import timezone

from apps.core.models import UserProfile
from apps.advertising.models import AdCampaignPlan, AdvertisingAccount, AdAgentDecision
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.services.campaign_service import CampaignService
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
        headlines = data.get('headlines') or []
        descriptions = data.get('descriptions') or []
        keywords = data.get('keywords') or []

        if litter and not (headlines and descriptions):
            user_profile = UserProfile.objects.filter(organization=organization).first()
            openai_api_key = getattr(getattr(organization, 'agent_config', None), 'openai_api_key', '') or ''
            generated = generate_ad_copy_with_fallback(
                litter=litter, user_profile=user_profile,
                audience_description=data.get('audience_description', ''), openai_api_key=openai_api_key,
            )
            headlines = headlines or generated['ad_headlines']
            descriptions = descriptions or generated['ad_descriptions']
            keywords = keywords or generated['ad_keywords']

        return AdCampaignPlan.objects.create(
            organization=organization,
            litter=litter,
            name=data.get('name') or (f'Ninhada {litter.name}' if litter else 'Campanha Google Ads'),
            daily_budget=data['daily_budget'],
            region=data.get('region', ''),
            radius_km=data.get('radius_km'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            landing_url=data.get('landing_url', ''),
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
                'ad_headlines': plan.headlines,
                'ad_descriptions': plan.descriptions,
                'ad_keywords': plan.keywords,
            },
            # Idempotência: se execute() for chamado de novo para o mesmo plano
            # (ex.: reenvio do tool call), não cria uma segunda campanha.
            client_request_id=f'plan-{plan.id}',
        )

        if plan.negative_keywords and campaign.external_campaign_id:
            try:
                CampaignService().add_negative_keywords(
                    organization, campaign.id, plan.negative_keywords,
                    reason='Negativas definidas no plano de campanha aprovado.', performed_by='agent',
                )
                campaign.refresh_from_db()
            except GoogleAdsProviderError:
                logger.exception('CampaignPlanService: falha ao aplicar negativas do plano')

        plan.status = 'executed'
        plan.resulting_campaign = campaign
        plan.decided_at = timezone.now()
        plan.save(update_fields=['status', 'resulting_campaign', 'decided_at'])

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
        )
        return campaign
