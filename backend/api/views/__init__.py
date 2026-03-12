import logging
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Organization, UserProfile, Plan, Subscription
from apps.leads.models import Lead, Note
from apps.conversations.models import Conversation, Message
from apps.quick_replies.models import QuickReply
from apps.channels.models import ChannelProvider
from apps.qualifier.engine import QualifierEngine

from api.serializers import (
    UserSerializer, LeadListSerializer, LeadDetailSerializer,
    MessageSerializer, NoteSerializer, QuickReplySerializer,
    ChannelProviderSerializer, PlanSerializer, SubscriptionSerializer,
)

logger = logging.getLogger(__name__)


def _get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UserSerializer(user).data,
    }


def _get_org(user):
    try:
        return user.profile.organization
    except Exception:
        return None


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = data.get('email', '').lower()
        password = data.get('password', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        org_name = data.get('organization_name', first_name + ' Org')

        if User.objects.filter(email=email).exists():
            return Response({'detail': 'Email já cadastrado.'}, status=400)

        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email, password=password,
                first_name=first_name, last_name=last_name,
            )
            org = Organization.objects.create(name=org_name)
            UserProfile.objects.create(user=user, organization=org, role='admin')
            free_plan = Plan.objects.filter(name='free').first()
            if free_plan:
                Subscription.objects.create(organization=org, plan=free_plan, status='trial')

        return Response(_get_tokens(user), status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        user = authenticate(request, username=email, password=password)
        if not user:
            try:
                u = User.objects.get(email=email)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass
        if not user:
            return Response({'detail': 'Credenciais inválidas.'}, status=401)
        return Response(_get_tokens(user))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ─── Leads ────────────────────────────────────────────────────────────────────

class LeadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['tier', 'status', 'source', 'is_ai_active']
    search_fields = ['phone', 'full_name', 'instagram_handle']
    ordering_fields = ['score', 'updated_at', 'created_at']

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return Lead.objects.none()
        return Lead.objects.filter(organization=org).select_related('assigned_to').prefetch_related('tags')

    def get_serializer_class(self):
        if self.action == 'list':
            return LeadListSerializer
        return LeadDetailSerializer

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        lead = self.get_object()
        try:
            conv = lead.conversation
            msgs = conv.messages.all()
            return Response(MessageSerializer(msgs, many=True).data)
        except Conversation.DoesNotExist:
            return Response([])

    @action(detail=True, methods=['post'])
    def assume(self, request, pk=None):
        lead = self.get_object()
        org = lead.organization
        lead.is_ai_active = False
        lead.assigned_to = request.user
        lead.status = 'HANDOFF'
        lead.save(update_fields=['is_ai_active', 'assigned_to', 'status'])
        conv, _ = Conversation.objects.get_or_create(
            lead=lead,
            defaults={'organization': org, 'channel': 'whatsapp', 'state': 'active'},
        )
        agent_name = request.user.first_name or request.user.email
        Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=f"👋 Atendimento assumido por {agent_name}.",
        )
        return Response(LeadDetailSerializer(lead).data)

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        lead = self.get_object()
        lead.is_ai_active = True
        lead.assigned_to = None
        lead.status = 'QUALIFYING' if lead.conversation_state not in ('complete', None) else lead.status
        lead.save(update_fields=['is_ai_active', 'assigned_to', 'status'])
        return Response(LeadDetailSerializer(lead).data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        lead = self.get_object()
        org = lead.organization
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)
        conv, _ = Conversation.objects.get_or_create(
            lead=lead,
            defaults={'organization': org, 'channel': 'whatsapp', 'state': 'active'},
        )
        msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=text,
        )
        # Send via WhatsApp if channel is active
        from apps.channels.models import ChannelProvider
        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider='whatsapp', is_active=True,
        ).first()
        if channel_provider and channel_provider.access_token and channel_provider.phone_number_id:
            _send_whatsapp_message(
                phone_number_id=channel_provider.phone_number_id,
                access_token=channel_provider.access_token,
                to=lead.phone,
                text=text,
            )
        return Response(MessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'])
    def send_file(self, request, pk=None):
        """Envia um arquivo (documento, imagem, PDF) via WhatsApp para o lead."""
        from rest_framework.parsers import MultiPartParser, FormParser
        from apps.channels.models import ChannelProvider
        import requests as http_requests
        import mimetypes
        import logging
        logger = logging.getLogger('apps')

        lead = self.get_object()
        org = lead.organization
        uploaded = request.FILES.get('file')
        caption = request.data.get('caption', '').strip()

        if not uploaded:
            return Response({'detail': 'Arquivo obrigatório.'}, status=400)

        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider='whatsapp', is_active=True,
        ).first()

        if not channel_provider or not channel_provider.access_token or not channel_provider.phone_number_id:
            return Response({'detail': 'Canal WhatsApp não configurado.'}, status=400)

        mime_type = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or 'application/octet-stream'
        is_image = mime_type.startswith('image/')

        # 1. Faz upload da mídia para o Meta e obtém media_id
        upload_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/media'
        try:
            upload_resp = http_requests.post(
                upload_url,
                headers={'Authorization': f'Bearer {channel_provider.access_token}'},
                files={'file': (uploaded.name, uploaded.read(), mime_type)},
                data={'messaging_product': 'whatsapp'},
                timeout=30,
            )
            if upload_resp.status_code != 200:
                logger.error(f'Media upload error: {upload_resp.status_code} {upload_resp.text}')
                return Response({'detail': f'Erro no upload: {upload_resp.text}'}, status=502)

            media_id = upload_resp.json().get('id')
        except Exception as e:
            logger.error(f'Media upload exception: {e}')
            return Response({'detail': f'Erro ao enviar arquivo: {str(e)}'}, status=500)

        # 2. Envia a mensagem com a mídia para o lead
        msg_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/messages'
        if is_image:
            media_payload = {
                'messaging_product': 'whatsapp',
                'to': lead.phone,
                'type': 'image',
                'image': {'id': media_id, 'caption': caption},
            }
        else:
            media_payload = {
                'messaging_product': 'whatsapp',
                'to': lead.phone,
                'type': 'document',
                'document': {'id': media_id, 'caption': caption, 'filename': uploaded.name},
            }

        try:
            send_resp = http_requests.post(
                msg_url,
                json=media_payload,
                headers={
                    'Authorization': f'Bearer {channel_provider.access_token}',
                    'Content-Type': 'application/json',
                },
                timeout=15,
            )
            if send_resp.status_code != 200:
                logger.error(f'Media send error: {send_resp.status_code} {send_resp.text}')
                return Response({'detail': f'Erro ao enviar: {send_resp.text}'}, status=502)
        except Exception as e:
            return Response({'detail': f'Erro ao enviar arquivo: {str(e)}'}, status=500)

        # 3. Salva no banco como mensagem OUT
        conv, _ = Conversation.objects.get_or_create(
            lead=lead,
            defaults={'organization': org, 'channel': 'whatsapp', 'state': 'active'},
        )
        label = caption or uploaded.name
        msg_text = f'📎 {uploaded.name}' + (f' — {caption}' if caption else '')
        msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=msg_text,
        )
        logger.info(f'File sent to {lead.phone}: {uploaded.name}')
        return Response(MessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'])
    def add_note(self, request, pk=None):
        lead = self.get_object()
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)
        note = Note.objects.create(lead=lead, author=request.user, text=text)
        return Response(NoteSerializer(note).data, status=201)

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        lead = self.get_object()
        lead.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'tier_a': qs.filter(tier='A').count(),
            'tier_b': qs.filter(tier='B').count(),
            'tier_c': qs.filter(tier='C').count(),
            'handoff': qs.filter(status='HANDOFF').count(),
            'qualifying': qs.filter(status='QUALIFYING').count(),
            'qualified': qs.filter(status='QUALIFIED').count(),
        })

    @action(detail=False, methods=['get'])
    def ab_stats(self, request):
        from django.db.models import Count, Q, Avg
        qs = self.get_queryset().filter(ab_variant__isnull=False).exclude(ab_variant='')
        rows = (
            qs.values('ab_variant')
            .annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(conversation_state='complete')),
                qualified=Count('id', filter=Q(status='QUALIFIED')),
                tier_a=Count('id', filter=Q(tier='A')),
                tier_b=Count('id', filter=Q(tier='B')),
                tier_c=Count('id', filter=Q(tier='C')),
                avg_score=Avg('score'),
            )
            .order_by('ab_variant')
        )
        return Response(list(rows))


# ─── Webhook ──────────────────────────────────────────────────────────────────

class WhatsAppWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        verify_token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge', '')
        if ChannelProvider.objects.filter(webhook_verify_token=verify_token).exists():
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type='text/plain', status=200)
        return Response({'detail': 'Invalid verify token.'}, status=403)

    def post(self, request):
        data = request.data

        # ── Detecta se é payload real da Meta ou payload do simulador interno ──
        is_meta_payload = data.get('object') == 'whatsapp_business_account'

        if is_meta_payload:
            return self._handle_meta_payload(data)
        else:
            return self._handle_simulator_payload(data)

    def _handle_meta_payload(self, data):
        """Processa o payload real enviado pela Meta Cloud API."""
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            # Ignora notificações que não são mensagens (ex: status de entrega)
            messages = value.get('messages')
            if not messages:
                return Response({'received': True}, status=200)

            msg = messages[0]
            msg_type = msg.get('type')
            from_phone = msg['from']
            phone_number_id = value['metadata']['phone_number_id']

            contacts = value.get('contacts', [])
            contact_name = contacts[0].get('profile', {}).get('name', '') if contacts else ''

            channel = ChannelProvider.objects.filter(phone_number_id=phone_number_id).first()
            if not channel or not channel.organization:
                return Response({'detail': 'Channel not found.'}, status=404)

            org = channel.organization

            # ── Mídia recebida (imagem, documento, áudio, vídeo) ──────────────
            MEDIA_TYPES = {'image', 'document', 'audio', 'video', 'sticker'}
            if msg_type in MEDIA_TYPES:
                return self._handle_incoming_media(
                    org=org, from_phone=from_phone, msg=msg,
                    msg_type=msg_type, channel=channel, contact_name=contact_name,
                )

            # ── Texto ─────────────────────────────────────────────────────────
            if msg_type != 'text':
                return Response({'received': True, 'note': f'type {msg_type} ignored'}, status=200)

            text = msg['text']['body'].strip()

        except (KeyError, IndexError) as e:
            import logging
            logging.getLogger('apps').error(f'Webhook Meta payload error: {e} | data: {data}')
            return Response({'received': True}, status=200)

        return self._process_message(org=org, from_phone=from_phone, text=text, provider='WHATSAPP', contact_name=contact_name)

    def _handle_incoming_media(self, org, from_phone, msg, msg_type, channel, contact_name=''):
        """Baixa mídia recebida do cliente, salva localmente e registra como mensagem IN."""
        import requests as http_requests
        import logging
        import os
        import uuid
        import mimetypes
        from django.utils import timezone
        from django.conf import settings
        logger = logging.getLogger('apps')

        media_data = msg.get(msg_type, {})
        media_id   = media_data.get('id', '')
        caption    = media_data.get('caption', '')
        filename   = media_data.get('filename', '')
        mime_type  = media_data.get('mime_type', '')

        # Detecta tipo real pelo MIME ou extensão do filename
        effective_type = msg_type
        if msg_type == 'document' and mime_type:
            if mime_type.startswith('image/'):
                effective_type = 'image'
            elif mime_type.startswith('video/'):
                effective_type = 'video'
            elif mime_type.startswith('audio/'):
                effective_type = 'audio'
        # Fallback pela extensão do filename
        if effective_type == 'document' and filename:
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif'}:
                effective_type = 'image'
            elif ext in {'mp4', 'mov', 'avi', 'mkv', '3gp'}:
                effective_type = 'video'
            elif ext in {'mp3', 'ogg', 'aac', 'm4a', 'opus'}:
                effective_type = 'audio'

        icons = {'image': '🖼️', 'document': '📄', 'audio': '🎵', 'video': '🎥', 'sticker': '🎭'}
        icon  = icons.get(effective_type, '📎')

        local_url = ''
        if media_id and channel.access_token:
            try:
                # 1. Obtém a URL de download temporária do Meta
                meta_resp = http_requests.get(
                    f'https://graph.facebook.com/v22.0/{media_id}',
                    headers={'Authorization': f'Bearer {channel.access_token}'},
                    timeout=10,
                )
                if meta_resp.status_code == 200:
                    download_url = meta_resp.json().get('url', '')
                    if download_url:
                        # 2. Baixa o arquivo com o token
                        dl_resp = http_requests.get(
                            download_url,
                            headers={'Authorization': f'Bearer {channel.access_token}'},
                            timeout=30,
                        )
                        if dl_resp.status_code == 200:
                            # 3. Determina extensão do arquivo
                            ext = mimetypes.guess_extension(mime_type.split(';')[0]) or ''
                            if ext == '.jpe': ext = '.jpg'
                            safe_name = filename or f'{msg_type}_{media_id[:8]}{ext}'
                            # Evita colisão de nomes
                            unique_name = f'{uuid.uuid4().hex[:8]}_{safe_name}'
                            save_dir = os.path.join(settings.MEDIA_ROOT, 'whatsapp')
                            os.makedirs(save_dir, exist_ok=True)
                            save_path = os.path.join(save_dir, unique_name)
                            with open(save_path, 'wb') as f:
                                f.write(dl_resp.content)
                            local_url = f'{settings.MEDIA_URL}whatsapp/{unique_name}'
                            logger.info(f'Media saved: {save_path}')
            except Exception as e:
                logger.warning(f'Could not download media {media_id}: {e}')

        # Monta texto da mensagem
        label = caption or filename or ''
        if local_url:
            text = f'{icon} {label}\n{local_url}' if label else f'{icon}\n{local_url}'
        else:
            text = f'{icon} {label or msg_type.capitalize()}'

        # Cria/busca lead e conversa
        lead, created = Lead.objects.get_or_create(
            organization=org,
            phone=from_phone,
            defaults={
                'status': 'NEW',
                'source': 'OTHER',
                'channels_used': 'whatsapp',
                'conversation_state': 'initial',
                'full_name': contact_name or '',
            }
        )
        if not created and contact_name and not lead.full_name:
            lead.full_name = contact_name
            lead.save(update_fields=['full_name'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead,
            defaults={'organization': org, 'channel': 'whatsapp', 'state': 'active'},
        )
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())

        Message.objects.create(
            conversation=conv,
            organization=org,
            direction='IN',
            text=text,
            provider_message_id=media_id,
        )
        logger.info(f'Incoming [{msg_type}] from {from_phone}: {label or media_id}')
        return Response({'received': True, 'type': msg_type})

    def _handle_simulator_payload(self, data):
        """Processa o payload do simulador interno (testes sem Meta)."""
        org_key = data.get('organization_key') or ''
        from_phone = data.get('from_phone', '')
        text = data.get('text', '').strip()
        provider = data.get('provider', 'WHATSAPP')

        try:
            org = Organization.objects.get(api_key=org_key)
        except Organization.DoesNotExist:
            return Response({'detail': 'Organization not found.'}, status=404)

        return self._process_message(org=org, from_phone=from_phone, text=text, provider=provider)

    def _process_message(self, org, from_phone, text, provider='WHATSAPP', contact_name=''):
        """Lógica comum: cria/atualiza lead, roda QualifierEngine, salva e envia mensagens."""
        from django.utils import timezone

        channel = provider.lower() if provider else 'whatsapp'

        lead, created = Lead.objects.get_or_create(
            organization=org,
            phone=from_phone,
            defaults={
                'status': 'NEW',
                'source': 'OTHER',
                'channels_used': channel,
                'conversation_state': 'initial',
                'full_name': contact_name or '',
            }
        )

        # Atualiza o nome se ainda não tinha e o Meta enviou agora
        if not created and contact_name and not lead.full_name:
            lead.full_name = contact_name
            lead.save(update_fields=['full_name'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead,
            defaults={
                'organization': org,
                'channel': channel,
                'state': 'active',
                'last_message_at': timezone.now(),
            }
        )
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())

        Message.objects.create(
            conversation=conv,
            organization=org,
            direction='IN',
            text=text,
        )

        if not lead.is_ai_active:
            return Response({'received': True, 'replies': [], 'lead': _lead_summary(lead)})

        engine = QualifierEngine(lead)
        replies = engine.process_message(text)

        # Busca o canal WhatsApp da organização para enviar as respostas
        channel_provider = ChannelProvider.objects.filter(
            organization=org,
            provider='whatsapp',
            is_active=True,
        ).first()

        reply_texts = []
        for reply in replies:
            is_media = isinstance(reply, dict)
            text = reply.get('caption', '') if is_media else reply

            Message.objects.create(
                conversation=conv,
                organization=org,
                direction='OUT',
                text=text,
            )
            reply_texts.append(text)

            if channel_provider and channel_provider.access_token and channel_provider.phone_number_id:
                if is_media:
                    _send_whatsapp_media(
                        phone_number_id=channel_provider.phone_number_id,
                        access_token=channel_provider.access_token,
                        to=from_phone,
                        media_type=reply.get('type', 'video'),
                        url=reply['url'],
                        caption=text,
                    )
                else:
                    _send_whatsapp_message(
                        phone_number_id=channel_provider.phone_number_id,
                        access_token=channel_provider.access_token,
                        to=from_phone,
                        text=reply,
                    )

        return Response({'received': True, 'replies': reply_texts, 'lead': _lead_summary(lead)})


def _send_whatsapp_message(phone_number_id, access_token, to, text):
    """Envia mensagem de texto via WhatsApp Cloud API."""
    import requests as http_requests
    import logging
    logger = logging.getLogger('apps')

    url = f'https://graph.facebook.com/v22.0/{phone_number_id}/messages'
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'body': text, 'preview_url': False},
    }
    try:
        resp = http_requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f'WhatsApp send error: {resp.status_code} {resp.text}')
        else:
            logger.info(f'WhatsApp message sent to {to}: {text[:50]}')
    except Exception as e:
        logger.error(f'WhatsApp send exception: {e}')


def _send_whatsapp_media(phone_number_id, access_token, to, media_type, url, caption=''):
    """Envia vídeo ou imagem via WhatsApp Cloud API usando link público."""
    import requests as http_requests
    import logging
    logger = logging.getLogger('apps')

    send_url = f'https://graph.facebook.com/v22.0/{phone_number_id}/messages'
    media_key = 'video' if media_type == 'video' else 'image'
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': media_key,
        media_key: {'link': url, 'caption': caption},
    }
    try:
        resp = http_requests.post(
            send_url,
            json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(f'WhatsApp media send error: {resp.status_code} {resp.text}')
        else:
            logger.info(f'WhatsApp {media_key} sent to {to}: {url[:60]}')
    except Exception as e:
        logger.error(f'WhatsApp media send exception: {e}')


def _lead_summary(lead):
    return {
        'id': lead.id,
        'tier': lead.tier,
        'score': lead.score,
        'status': lead.status,
        'is_ai_active': lead.is_ai_active,
        'conversation_state': lead.conversation_state,
    }


# ─── Channels ─────────────────────────────────────────────────────────────────

class ChannelProviderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ChannelProviderSerializer

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return ChannelProvider.objects.none()
        return ChannelProvider.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)


# ─── Quick Replies ─────────────────────────────────────────────────────────────

class QuickReplyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = QuickReplySerializer

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return QuickReply.objects.none()
        return QuickReply.objects.filter(organization=org, is_active=True)

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)


# ─── Plans & Subscriptions ────────────────────────────────────────────────────

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        try:
            sub = org.subscription
            return Response(SubscriptionSerializer(sub).data)
        except Subscription.DoesNotExist:
            return Response({'detail': 'No subscription.'}, status=404)

    def post(self, request):
        """Upgrade/change plan."""
        org = _get_org(request.user)
        plan_name = request.data.get('plan')
        try:
            plan = Plan.objects.get(name=plan_name)
        except Plan.DoesNotExist:
            return Response({'detail': 'Invalid plan.'}, status=400)
        sub, _ = Subscription.objects.get_or_create(
            organization=org,
            defaults={'plan': plan, 'status': 'active'},
        )
        sub.plan = plan
        sub.status = 'active'
        sub.save()
        return Response(SubscriptionSerializer(sub).data)
