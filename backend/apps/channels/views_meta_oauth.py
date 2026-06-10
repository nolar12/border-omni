"""
Meta OAuth views — Business Integration System User Token (SUAT) flow.

Flow:
  1. Frontend calls FB.login() with config_id + response_type=code
  2. Frontend sends code to MetaOAuthDiscoverView
  3. Backend exchanges code for SUAT and lists available assets (WABAs, Pages)
  4. Frontend shows asset selection to user
  5. Frontend sends selection to MetaOAuthFinalizeView
  6. Backend configures webhooks via API and saves ChannelProvider
"""
import secrets
import logging

from django.conf import settings
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.channels.models import ChannelProvider
from apps.core.models import Organization, UserProfile
from apps.channels.meta_client import (
    exchange_code_for_suat,
    get_waba_assets,
    get_page_assets,
    subscribe_waba_webhook,
    subscribe_page_webhook,
    verify_phone_number,
)
from api.serializers import ChannelProviderSerializer

logger = logging.getLogger('apps')


def _get_org(user):
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


class MetaOAuthDiscoverView(APIView):
    """
    Step 1: exchange the FB.login() code for a SUAT and return the list of
    Meta business assets the user can connect (WABAs or Pages).
    Does NOT create or modify any ChannelProvider.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip()
        provider = request.data.get('provider', 'whatsapp')

        if not code:
            return Response({'error': 'code é obrigatório'}, status=400)

        app_id = getattr(settings, 'META_APP_ID', '')
        app_secret = getattr(settings, 'META_APP_SECRET', '')

        if not app_id or not app_secret:
            return Response(
                {'error': 'Integração Meta não configurada no servidor (META_APP_ID / META_APP_SECRET).'},
                status=503,
            )

        # Exchange code for SUAT (server-to-server — never touches client's personal account)
        try:
            suat = exchange_code_for_suat(code, app_id, app_secret)
        except Exception as exc:
            logger.exception('MetaOAuthDiscover: failed to exchange code')
            return Response({'error': f'Falha ao autenticar com a Meta: {exc}'}, status=400)

        # Discover assets
        try:
            if provider == 'whatsapp':
                assets = get_waba_assets(suat)
            else:
                assets = get_page_assets(suat)
        except Exception as exc:
            logger.exception('MetaOAuthDiscover: failed to list assets')
            return Response({'error': f'Falha ao listar contas Meta: {exc}'}, status=400)

        return Response({
            'provider': provider,
            'access_token': suat,   # passed back in the finalize step (stays in React state only)
            'assets': assets,
        })


class MetaOAuthFinalizeView(APIView):
    """
    Step 2: user has selected which account to connect.
    Backend configures webhooks via API and saves (or updates) ChannelProvider.
    The SUAT is stored as access_token — it belongs to the Business Portfolio, not any person.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = request.data.get('provider', '').strip()
        name = request.data.get('name', '').strip()
        suat = request.data.get('access_token', '').strip()

        if not provider or not suat:
            return Response({'error': 'provider e access_token são obrigatórios'}, status=400)

        org = _get_org(request.user)
        if not org:
            return Response({'error': 'Organização não encontrada para este usuário'}, status=400)

        app_id = getattr(settings, 'META_APP_ID', '')
        app_secret = getattr(settings, 'META_APP_SECRET', '')
        webhook_base = getattr(settings, 'META_WEBHOOK_BASE_URL', '').rstrip('/')

        if not app_id or not app_secret or not webhook_base:
            return Response(
                {'error': 'Integração Meta não completamente configurada no servidor.'},
                status=503,
            )

        # App-level token used for WABA webhook subscription (not the client's token)
        app_token = f'{app_id}|{app_secret}'
        verify_token = secrets.token_urlsafe(32)

        try:
            if provider == 'whatsapp':
                channel, created = self._connect_whatsapp(
                    request, org, name, suat, app_token, app_id, webhook_base, verify_token,
                )
            elif provider in ('facebook', 'messenger'):
                channel, created = self._connect_page(
                    request, org, provider, name, app_id, webhook_base, verify_token,
                )
            elif provider == 'instagram':
                channel, created = self._connect_instagram(
                    request, org, name, app_id, webhook_base, verify_token,
                )
            else:
                return Response({'error': f'Provider não suportado: {provider}'}, status=400)

        except Exception as exc:
            logger.exception('MetaOAuthFinalize: failed to configure channel')
            return Response({'error': f'Falha ao configurar canal: {exc}'}, status=400)

        return Response(
            ChannelProviderSerializer(channel).data,
            status=201 if created else 200,
        )

    # ── private helpers ────────────────────────────────────────────────────────

    def _connect_whatsapp(
        self, request, org, name, suat, app_token, app_id, webhook_base, verify_token,
    ):
        waba_id = request.data.get('waba_id', '').strip()
        phone_number_id = request.data.get('phone_number_id', '').strip()

        if not waba_id or not phone_number_id:
            raise ValueError('waba_id e phone_number_id são obrigatórios para WhatsApp')

        webhook_url = f'{webhook_base}/api/webhooks/whatsapp/'

        # Configure webhook via API — no manual Meta dashboard step needed
        subscribe_waba_webhook(waba_id, app_token, webhook_url, verify_token)

        # Verify the phone number is healthy
        try:
            phone_info = verify_phone_number(phone_number_id, suat)
            verified_name = phone_info.get('verified_name', '')
        except Exception:
            verified_name = ''

        channel_name = name or verified_name or 'WhatsApp Business'

        channel, created = ChannelProvider.objects.update_or_create(
            organization=org,
            provider='whatsapp',
            business_account_id=waba_id,
            defaults={
                'name': channel_name,
                'access_token': suat,
                'app_id': app_id,
                'app_secret': '',
                'phone_number_id': phone_number_id,
                'webhook_verify_token': verify_token,
                'webhook_url': webhook_url,
                'is_active': True,
                'verification_status': 'verified',
                'last_verified_at': timezone.now(),
            },
        )
        return channel, created

    def _connect_page(self, request, org, provider, name, app_id, webhook_base, verify_token):
        page_id = request.data.get('page_id', '').strip()
        page_token = request.data.get('page_token', '').strip()
        page_name = request.data.get('page_name', '').strip()

        if not page_id or not page_token:
            raise ValueError('page_id e page_token são obrigatórios para Facebook/Messenger')

        webhook_url = f'{webhook_base}/api/webhooks/meta/'
        fields = ['messages', 'messaging_postbacks', 'messaging_referrals',
                  'message_deliveries', 'message_reads']
        subscribe_page_webhook(page_id, page_token, fields)

        channel, created = ChannelProvider.objects.update_or_create(
            organization=org,
            provider=provider,
            page_id=page_id,
            defaults={
                'name': name or page_name or 'Facebook Page',
                'access_token': page_token,
                'app_id': app_id,
                'app_secret': '',
                'page_id': page_id,
                'webhook_verify_token': verify_token,
                'webhook_url': webhook_url,
                'is_active': True,
                'verification_status': 'verified',
                'last_verified_at': timezone.now(),
            },
        )
        return channel, created

    def _connect_instagram(self, request, org, name, app_id, webhook_base, verify_token):
        page_id = request.data.get('page_id', '').strip()
        page_token = request.data.get('page_token', '').strip()
        instagram_account_id = request.data.get('instagram_account_id', '').strip()
        ig_username = request.data.get('instagram_username', '').strip()
        page_name = request.data.get('page_name', '').strip()

        if not page_id or not page_token or not instagram_account_id:
            raise ValueError('page_id, page_token e instagram_account_id são obrigatórios para Instagram')

        webhook_url = f'{webhook_base}/api/webhooks/meta/'
        fields = ['messages', 'messaging_postbacks', 'instagram_manage_messages']
        subscribe_page_webhook(page_id, page_token, fields)

        channel, created = ChannelProvider.objects.update_or_create(
            organization=org,
            provider='instagram',
            instagram_account_id=instagram_account_id,
            defaults={
                'name': name or (f'@{ig_username}' if ig_username else page_name) or 'Instagram',
                'access_token': page_token,
                'app_id': app_id,
                'app_secret': '',
                'page_id': page_id,
                'instagram_account_id': instagram_account_id,
                'webhook_verify_token': verify_token,
                'webhook_url': webhook_url,
                'is_active': True,
                'verification_status': 'verified',
                'last_verified_at': timezone.now(),
            },
        )
        return channel, created
