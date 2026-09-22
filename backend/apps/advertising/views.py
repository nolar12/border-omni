import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Organization, UserProfile
from apps.kennel.models import Litter
from apps.leads.models import Lead, LeadProfile
from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdvertisingSettings, AdClickToken, AdEvent, AdCampaignBriefing,
)
from apps.advertising.providers import GoogleAdsProviderError, exchange_code_for_tokens, list_accessible_customers
from apps.advertising.services.campaign_service import CampaignService
from apps.advertising.services.metrics_service import MetricsService
from apps.advertising.services.conversion_service import ConversionService
from apps.advertising.services.ai_copy_service import generate_ad_copy_with_fallback
from apps.advertising.services.agent_service import AdvertisingAgentService
from apps.advertising.services.transcription_service import transcribe_audio_file
from apps.advertising.services import lead_funnel_service
from apps.advertising.serializers import (
    AdvertisingAccountSerializer, AdCampaignSerializer, AdCampaignDetailSerializer,
    AdMetricSerializer, AdvertisingSettingsSerializer,
    PublicAdClickTokenRequestSerializer, AdClickTokenResponseSerializer, AdChatMessageSerializer,
    AdCampaignBriefingSerializer, AdAgentDecisionSerializer,
)

logger = logging.getLogger('apps')


def _get_org(user):
    """
    Réplica intencional do helper homônimo em api/views/__init__.py — evita acoplar
    esta app a um símbolo "privado" (com underscore) de outro módulo.
    """
    try:
        org_id = (
            UserProfile.objects
            .filter(user_id=user.id)
            .values_list('organization_id', flat=True)
            .first()
        )
        if not org_id:
            return None
        return Organization.objects.filter(id=org_id).first()
    except Exception:
        return None


class AdvertisingAccountViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertisingAccountSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return AdvertisingAccount.objects.none()
        return AdvertisingAccount.objects.filter(organization=org)

    def perform_create(self, serializer):
        serializer.save(organization=_get_org(self.request.user))


class AdCampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return AdCampaign.objects.none()
        return AdCampaign.objects.filter(organization=org)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdCampaignDetailSerializer
        return AdCampaignSerializer

    @action(detail=False, methods=['post'], url_path='promote-litter')
    def promote_litter(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada para este usuário.'}, status=400)

        litter_id = request.data.get('litter_id')
        litter = Litter.objects.filter(id=litter_id, organization=org).first() if litter_id else None
        if litter_id and not litter:
            return Response({'error': 'Ninhada não encontrada.'}, status=404)

        account = AdvertisingAccount.objects.filter(organization=org, is_active=True).first()
        if not account:
            return Response(
                {'error': 'Nenhuma conta de anúncios conectada. Conecte uma conta Google Ads primeiro.'},
                status=400,
            )

        data = dict(request.data)
        data.setdefault('name', f'Ninhada {litter.name}' if litter else 'Campanha Google Ads')
        if not data.get('ad_headlines') and litter:
            profile = UserProfile.objects.filter(organization=org).first()
            audience_description = (request.data.get('audience_description') or '').strip()
            openai_api_key = getattr(getattr(org, 'agent_config', None), 'openai_api_key', '') or ''
            data.update(generate_ad_copy_with_fallback(
                litter=litter, user_profile=profile,
                audience_description=audience_description, openai_api_key=openai_api_key,
            ))

        campaign = CampaignService().create_campaign(
            organization=org,
            advertising_account=account,
            litter=litter,
            data=data,
            client_request_id=request.data.get('client_request_id'),
        )
        return Response(AdCampaignSerializer(campaign).data, status=201)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        org = _get_org(request.user)
        try:
            campaign = CampaignService().pause_campaign(org, int(pk))
        except AdCampaign.DoesNotExist:
            return Response({'error': 'Campanha não encontrada.'}, status=404)
        return Response(AdCampaignSerializer(campaign).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        org = _get_org(request.user)
        try:
            campaign = CampaignService().resume_campaign(org, int(pk))
        except AdCampaign.DoesNotExist:
            return Response({'error': 'Campanha não encontrada.'}, status=404)
        return Response(AdCampaignSerializer(campaign).data)

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        campaign = self.get_object()
        return Response(AdMetricSerializer(campaign.metrics.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='sync_metrics')
    def sync_metrics(self, request, pk=None):
        campaign = self.get_object()
        try:
            synced = MetricsService().sync_campaign_metrics(campaign)
        except GoogleAdsProviderError as exc:
            return Response({'error': exc.user_message}, status=400)
        return Response({'synced': synced, 'metrics': AdMetricSerializer(campaign.metrics.all(), many=True).data})

    @action(detail=True, methods=['get', 'post'], url_path='chat')
    def chat(self, request, pk=None):
        campaign = self.get_object()

        if request.method == 'GET':
            return Response(AdChatMessageSerializer(campaign.chat_messages.all(), many=True).data)

        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({'error': 'message é obrigatório'}, status=400)

        openai_api_key = getattr(getattr(campaign.organization, 'agent_config', None), 'openai_api_key', '') or ''
        if not openai_api_key:
            return Response(
                {'error': 'Nenhuma OpenAI API key configurada para esta organização (Configurações → IA).'},
                status=503,
            )

        reply = AdvertisingAgentService(campaign).chat(user_message=message, openai_api_key=openai_api_key)
        return Response(AdChatMessageSerializer(reply).data, status=201)

    @action(detail=True, methods=['post'], url_path='chat/transcribe')
    def transcribe(self, request, pk=None):
        campaign = self.get_object()
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response({'error': 'audio é obrigatório'}, status=400)

        openai_api_key = getattr(getattr(campaign.organization, 'agent_config', None), 'openai_api_key', '') or ''
        if not openai_api_key:
            return Response(
                {'error': 'Nenhuma OpenAI API key configurada para esta organização (Configurações → IA).'},
                status=503,
            )

        try:
            text = transcribe_audio_file(audio_file, openai_api_key)
        except Exception as exc:
            logger.exception('AdCampaignViewSet.transcribe failed')
            return Response({'error': f'Falha ao transcrever áudio: {exc}'}, status=400)

        return Response({'transcription': text})

    @action(detail=True, methods=['post'], url_path='chat/proactive-review')
    def proactive_review(self, request, pk=None):
        """Dispara manualmente a mesma revisão que roda sozinha semanalmente
        (só leitura) — útil para testar/forçar sem esperar o agendamento."""
        campaign = self.get_object()
        openai_api_key = getattr(getattr(campaign.organization, 'agent_config', None), 'openai_api_key', '') or ''
        if not openai_api_key:
            return Response(
                {'error': 'Nenhuma OpenAI API key configurada para esta organização (Configurações → IA).'},
                status=503,
            )

        try:
            MetricsService().sync_campaign_metrics(campaign)
        except GoogleAdsProviderError:
            logger.warning('proactive_review: falha ao sincronizar métricas antes da revisão')

        message = AdvertisingAgentService(campaign).run_proactive_review(openai_api_key=openai_api_key)
        if not message:
            return Response({'status': 'nothing_to_report'})
        return Response(AdChatMessageSerializer(message).data, status=201)

    @action(detail=True, methods=['get', 'put'], url_path='briefing')
    def briefing(self, request, pk=None):
        campaign = self.get_object()
        obj, _ = AdCampaignBriefing.objects.get_or_create(campaign=campaign)

        if request.method == 'GET':
            return Response(AdCampaignBriefingSerializer(obj).data)

        serializer = AdCampaignBriefingSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='decisions')
    def decisions(self, request, pk=None):
        campaign = self.get_object()
        return Response(AdAgentDecisionSerializer(campaign.agent_decisions.all()[:50], many=True).data)

    @action(detail=True, methods=['get'], url_path='funnel')
    def funnel(self, request, pk=None):
        campaign = self.get_object()
        return Response(lead_funnel_service.funnel_summary(campaign))

    @action(detail=True, methods=['get'], url_path='dashboard')
    def dashboard(self, request, pk=None):
        """
        Visão consolidada pra tela de Anúncios: o mesmo snapshot (custo, leads,
        qualificados, negociações, reservas, vendas, CPL/CPL qualificado/CAC) que
        já alimenta as decisões do agente, mais a quebra por cidade e por
        keyword (dado comercial do CRM — sem gasto por grupo, essa quebra não
        existe no Google Ads ainda). `days_back` filtra o período (padrão 30).
        """
        campaign = self.get_object()
        try:
            days_back = int(request.query_params.get('days_back', 30))
        except ValueError:
            return Response({'error': 'days_back deve ser um número inteiro de dias.'}, status=400)

        return Response({
            'snapshot': MetricsService().build_snapshot(campaign, days_back=days_back),
            'city_breakdown': lead_funnel_service.breakdown_by_city(campaign),
            'keyword_breakdown': lead_funnel_service.breakdown_by_keyword(campaign),
        })


class AdvertisingSettingsView(APIView):
    """Mesmo padrão de AgentConfigView (api/views/__init__.py) — GET/PUT, get_or_create por org."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada.'}, status=400)
        obj, _ = AdvertisingSettings.objects.get_or_create(organization=org)
        return Response(AdvertisingSettingsSerializer(obj).data)

    def put(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada.'}, status=400)
        obj, _ = AdvertisingSettings.objects.get_or_create(organization=org)
        serializer = AdvertisingSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GoogleAdsOAuthDiscoverView(APIView):
    """
    Passo 1: troca o authorization code (obtido no frontend via Google Identity
    Services, google.accounts.oauth2.initCodeClient com ux_mode: 'popup' — mesma
    filosofia do FB.login() popup usado para o Meta, sem redirect de página cheia)
    pelo refresh_token, e lista as contas Google Ads acessíveis.

    Importante: no fluxo popup do GIS, o code exchange usa redirect_uri="postmessage"
    (valor especial documentado pelo Google), não uma URL real — por isso não é
    necessário registrar nenhum "URI de redirecionamento" no Google Cloud Console,
    apenas a origem do frontend em "Authorized JavaScript origins".
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip()
        if not code:
            return Response({'error': 'code é obrigatório'}, status=400)
        if not settings.GOOGLE_ADS_CLIENT_ID or not settings.GOOGLE_ADS_CLIENT_SECRET:
            return Response({'error': 'Integração Google Ads não configurada no servidor (GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET).'}, status=503)
        if not settings.GOOGLE_ADS_DEVELOPER_TOKEN:
            return Response({'error': 'GOOGLE_ADS_DEVELOPER_TOKEN não configurado no servidor.'}, status=503)

        try:
            tokens = exchange_code_for_tokens(
                code, settings.GOOGLE_ADS_CLIENT_ID, settings.GOOGLE_ADS_CLIENT_SECRET,
                redirect_uri='postmessage',
            )
            customers = list_accessible_customers(tokens['access_token'], settings.GOOGLE_ADS_DEVELOPER_TOKEN)
        except GoogleAdsProviderError as exc:
            return Response({'error': exc.user_message}, status=400)

        return Response({
            'refresh_token': tokens['refresh_token'],  # mantido só no estado do React, mesma lógica do Meta discover
            'accessible_customers': customers,
        })


class GoogleAdsOAuthFinalizeView(APIView):
    """Passo 2: usuário escolheu o customer_id — persiste a AdvertisingAccount."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada para este usuário.'}, status=400)

        refresh_token = request.data.get('refresh_token', '').strip()
        customer_id = request.data.get('customer_id', '').strip()
        login_customer_id = request.data.get('login_customer_id', '').strip()
        if not refresh_token or not customer_id:
            return Response({'error': 'refresh_token e customer_id são obrigatórios'}, status=400)

        account, created = AdvertisingAccount.objects.update_or_create(
            organization=org, provider='google_ads', customer_id=customer_id,
            defaults={
                'refresh_token': refresh_token,
                'login_customer_id': login_customer_id,
                'status': 'connected',
                'is_active': True,
            },
        )
        return Response(AdvertisingAccountSerializer(account).data, status=201 if created else 200)


class PublicAdClickTokenView(APIView):
    """
    Endpoint público (sem auth) chamado pela landing page (bordercollie-sul) quando
    detecta gclid/UTM na URL. Cria um AdClickToken curto para religar o eventual
    clique de WhatsApp ao Lead, e registra um AdEvent de page_view.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PublicAdClickTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org = Organization.objects.filter(id=data['org_id']).first()
        if not org:
            return Response({'error': 'Organização inválida.'}, status=404)

        litter = None
        litter_id = data.get('litter_id')
        if litter_id:
            litter = Litter.objects.filter(id=litter_id, organization=org).first()

        click_token = AdClickToken.objects.create(
            organization=org,
            gclid=data.get('gclid', ''),
            gbraid=data.get('gbraid', ''),
            wbraid=data.get('wbraid', ''),
            utm_source=data.get('utm_source', ''),
            utm_medium=data.get('utm_medium', ''),
            utm_campaign=data.get('utm_campaign', ''),
            utm_content=data.get('utm_content', ''),
            ad_group_id=data.get('ad_group_id', ''),
            ad_id=data.get('ad_id', ''),
            keyword=data.get('keyword', ''),
            search_term=data.get('search_term', ''),
            litter=litter,
        )
        AdEvent.objects.create(
            organization=org, event_type='page_view',
            metadata={'gclid': click_token.gclid, 'utm_source': click_token.utm_source, 'litter_id': litter_id},
        )

        return Response(AdClickTokenResponseSerializer(click_token).data, status=201)


class LeadCommercialEventView(APIView):
    """
    Fecha o ciclo Google Ads → CRM → Google Ads: hoje é o ÚNICO lugar do sistema
    que marca LeadProfile.is_reserved/is_purchased (usados pelo funil comercial
    em lead_funnel_service e por essas mesmas duas flags aqui) — antes desta view
    esses campos existiam no model mas nada os definia. Ao marcar reserva/venda,
    dispara ConversionService.record_event, que envia o sinal de conversão
    (RESERVED/SOLD) ao Google Ads via Data Manager API quando há atribuição de
    clique (gclid/gbraid/wbraid) para o lead.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):
        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada para este usuário.'}, status=400)

        event_type = request.data.get('event_type')
        if event_type not in ('reservation', 'sale'):
            return Response({'error': 'event_type deve ser "reservation" ou "sale".'}, status=400)

        try:
            lead = Lead.objects.get(organization=org, id=lead_id)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead não encontrado.'}, status=404)

        profile, _ = LeadProfile.objects.get_or_create(lead=lead)
        already_recorded = profile.is_purchased if event_type == 'sale' else profile.is_reserved
        if already_recorded:
            return Response({
                'status': 'already_recorded', 'is_reserved': profile.is_reserved, 'is_purchased': profile.is_purchased,
            })

        if event_type == 'sale':
            profile.is_reserved = True
            profile.is_purchased = True
            profile.save(update_fields=['is_reserved', 'is_purchased'])
        else:
            profile.is_reserved = True
            profile.save(update_fields=['is_reserved'])

        raw_value = request.data.get('value')
        value = None
        if raw_value not in (None, ''):
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return Response({'error': 'value precisa ser um número.'}, status=400)

        ConversionService().record_event(organization=org, lead=lead, event_type=event_type, value=value)

        return Response({'status': 'recorded', 'is_reserved': profile.is_reserved, 'is_purchased': profile.is_purchased})


class OnyxDigestSummaryView(APIView):
    """
    GET /api/advertising/onyx-digest-summary/?date=YYYY-MM-DD

    Endpoint de LEITURA consumido pelo digest diário do Onyx (projeto separado, 12 Habits/
    habit-backend) — Onyx puxa daqui uma vez por dia; este projeto nunca chama o Onyx (o
    endpoint de ingestão de lá exige JWT do dono + owner-gate, incompatível com um cron
    externo). Protegido por chave compartilhada simples (ONYX_PULL_API_KEY), não por
    autenticação de usuário — não há usuário autenticado do lado de quem chama.

    Resposta pensada para virar bullets de "### Projeto: <nome>" no digest narrativo do
    Onyx: métricas do dia + decisões reais do AdAgentDecision (mesma auditoria usada nas
    respostas do chat de campanha), nunca números inventados.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        expected_key = getattr(settings, 'ONYX_PULL_API_KEY', '')
        provided_key = request.headers.get('X-Onyx-Pull-Key', '')
        if not expected_key or provided_key != expected_key:
            return Response({'error': 'Não autorizado.'}, status=403)

        date_param = request.query_params.get('date')
        if date_param:
            try:
                target_date = timezone.datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'date deve estar no formato YYYY-MM-DD.'}, status=400)
        else:
            target_date = timezone.localdate()

        day_start = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        day_end = day_start + timezone.timedelta(days=1)

        campaigns_payload = []
        for campaign in AdCampaign.objects.filter(status__in=['active', 'paused']).select_related('organization'):
            decisions = AdAgentDecisionSerializer(
                campaign.agent_decisions.filter(created_at__gte=day_start, created_at__lt=day_end).order_by('created_at'),
                many=True,
            ).data
            try:
                snapshot = MetricsService().build_snapshot(campaign, days_back=1)
            except Exception:
                logger.exception('OnyxDigestSummaryView: build_snapshot falhou para campaign=%s', campaign.id)
                snapshot = None

            if not decisions and (not snapshot or not snapshot.get('impressions')):
                continue  # dia sem nenhuma atividade nesta campanha — não polui o digest

            campaigns_payload.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'metrics': snapshot,
                'decisions': decisions,
            })

        return Response({'date': target_date.isoformat(), 'campaigns': campaigns_payload})
