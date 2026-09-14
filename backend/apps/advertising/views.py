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
from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdvertisingSettings, AdClickToken, AdEvent,
)
from apps.advertising.providers import GoogleAdsProviderError, exchange_code_for_tokens, list_accessible_customers
from apps.advertising.services.campaign_service import CampaignService
from apps.advertising.services.ai_copy_service import generate_ad_copy_with_fallback
from apps.advertising.serializers import (
    AdvertisingAccountSerializer, AdCampaignSerializer, AdCampaignDetailSerializer,
    AdMetricSerializer, AdvertisingSettingsSerializer,
    PublicAdClickTokenRequestSerializer, AdClickTokenResponseSerializer,
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
            utm_source=data.get('utm_source', ''),
            utm_medium=data.get('utm_medium', ''),
            utm_campaign=data.get('utm_campaign', ''),
            utm_content=data.get('utm_content', ''),
            litter=litter,
        )
        AdEvent.objects.create(
            organization=org, event_type='page_view',
            metadata={'gclid': click_token.gclid, 'utm_source': click_token.utm_source, 'litter_id': litter_id},
        )

        return Response(AdClickTokenResponseSerializer(click_token).data, status=201)
