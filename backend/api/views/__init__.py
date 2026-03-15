import logging
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Organization, UserProfile, Plan, Subscription, AgentConfig, InitialMessageMedia
from apps.leads.models import Lead, Note
from apps.conversations.models import Conversation, Message
from apps.quick_replies.models import QuickReply, QuickReplyCategory
from apps.channels.models import ChannelProvider
from apps.qualifier.engine import QualifierEngine

from api.serializers import (
    UserSerializer, LeadListSerializer, LeadDetailSerializer,
    MessageSerializer, NoteSerializer,
    QuickReplySerializer, QuickReplyCategorySerializer,
    ChannelProviderSerializer, PlanSerializer, SubscriptionSerializer,
    AgentConfigSerializer, InitialMessageMediaSerializer,
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

class LeadViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
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
        channel = request.query_params.get('channel')
        qs = Message.objects.filter(conversation__lead=lead).order_by('created_at')
        if channel:
            qs = qs.filter(conversation__channel=channel)
        return Response(MessageSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def assume(self, request, pk=None):
        lead = self.get_object()
        org = lead.organization
        lead.is_ai_active = False
        lead.assigned_to = request.user
        lead.status = 'HANDOFF'
        lead.save(update_fields=['is_ai_active', 'assigned_to', 'status'])
        active_conv = lead.conversations.order_by('-last_message_at').first()
        if not active_conv:
            active_conv, _ = Conversation.objects.get_or_create(
                lead=lead, channel='whatsapp',
                defaults={'organization': org, 'state': 'active'},
            )
        agent_name = request.user.first_name or request.user.email
        Message.objects.create(
            conversation=active_conv,
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

        # Usa a conversa mais recente do lead; default para whatsapp se ainda não existe
        active_conv = lead.conversations.order_by('-last_message_at').first()
        if not active_conv:
            active_conv, _ = Conversation.objects.get_or_create(
                lead=lead, channel='whatsapp',
                defaults={'organization': org, 'state': 'active'},
            )
        channel = active_conv.channel

        # Captura última mensagem IN para armazenar o par de treinamento
        last_in = (
            Message.objects.filter(conversation=active_conv, direction='IN')
            .order_by('-created_at').first()
        )

        msg = Message.objects.create(
            conversation=active_conv,
            organization=org,
            direction='OUT',
            text=text,
            msg_status='sent',
        )

        from apps.channels.models import ChannelProvider
        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider=channel, is_active=True,
        ).first()

        if channel_provider and channel_provider.access_token:
            if channel in ('messenger', 'facebook'):
                _send_facebook_message(
                    page_id=channel_provider.page_id,
                    access_token=channel_provider.access_token,
                    recipient_id=lead.facebook_psid or '',
                    text=text,
                )
            elif channel == 'instagram':
                _send_instagram_message(
                    instagram_account_id=channel_provider.instagram_account_id,
                    access_token=channel_provider.access_token,
                    recipient_id=lead.instagram_user_id or '',
                    text=text,
                )
            elif channel_provider.phone_number_id:
                wamid = _send_whatsapp_message(
                    phone_number_id=channel_provider.phone_number_id,
                    access_token=channel_provider.access_token,
                    to=lead.phone,
                    text=text,
                )
                if wamid:
                    Message.objects.filter(pk=msg.pk).update(provider_message_id=wamid)
                    msg.provider_message_id = wamid

        # Coleta de dados de treinamento em background (não bloqueia a resposta)
        if last_in:
            try:
                agent_config = org.agent_config
                if agent_config and agent_config.is_ready():
                    from apps.rag.services.training_service import store_conversation_pair
                    store_conversation_pair(agent_config, last_in.text, text, lead)
            except AgentConfig.DoesNotExist:
                pass
            except Exception:
                pass

        return Response(MessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'])
    def enhance_message(self, request, pk=None):
        """
        Pré-visualização de cordialidade.
        Transforma o texto via IA mas NÃO salva nem envia nada.
        Retorna: { original, enhanced, changed }
        """
        lead = self.get_object()
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)

        enhanced = text
        try:
            agent_config = lead.organization.agent_config
            if agent_config and getattr(agent_config, 'cordiality_enabled', False):
                from apps.rag.services.cordiality_service import CordialityEnhancementService
                enhanced = CordialityEnhancementService(agent_config, lead).enhance(text)
        except AgentConfig.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f'enhance_message error: {e}')

        return Response({
            'original': text,
            'enhanced': enhanced,
            'changed': enhanced != text,
        })

    @action(detail=True, methods=['post'])
    def suggest_response(self, request, pk=None):
        """Gera sugestão de resposta RAG para o atendente. Não envia nada."""
        lead = self.get_object()
        org = lead.organization
        message_text = request.data.get('message', '').strip()
        if not message_text:
            return Response({'suggestion': None})

        try:
            agent_config = org.agent_config
        except AgentConfig.DoesNotExist:
            return Response({'suggestion': None})

        if not agent_config.is_ready():
            return Response({'suggestion': None})

        try:
            from apps.rag.services.rag_service import RAGService
            suggestion = RAGService(agent_config).suggest(lead, message_text)
        except Exception as e:
            logger.warning(f'suggest_response error: {e}')
            suggestion = None

        return Response({'suggestion': suggestion})

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
            lead=lead, channel='whatsapp',
            defaults={'organization': org, 'state': 'active'},
        )
        msg_text = f'📎 {uploaded.name}' + (f' — {caption}' if caption else '')
        wamid_file = send_resp.json().get('messages', [{}])[0].get('id')
        msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=msg_text,
            provider_message_id=wamid_file,
            msg_status='sent',
        )
        logger.info(f'File sent to {lead.phone}: {uploaded.name} | wamid={wamid_file}')
        return Response(MessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'])
    def add_note(self, request, pk=None):
        lead = self.get_object()
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)
        note = Note.objects.create(lead=lead, author=request.user, text=text)
        return Response(NoteSerializer(note).data, status=201)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        lead = self.get_object()
        lead.status = 'CLOSED'
        lead.is_ai_active = False
        lead.save(update_fields=['status', 'is_ai_active'])
        return Response(LeadDetailSerializer(lead).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        lead = self.get_object()
        lead.status = 'QUALIFIED'
        lead.save(update_fields=['status'])
        return Response(LeadDetailSerializer(lead).data)

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

            # ── Status de entrega/leitura (sent → delivered → read) ───────────
            statuses = value.get('statuses')
            if statuses:
                return self._handle_status_update(statuses)

            # Ignora notificações que não são mensagens
            messages = value.get('messages')
            if not messages:
                return Response({'received': True}, status=200)

            msg = messages[0]
            msg_type = msg.get('type')
            from_phone = msg['from']
            phone_number_id = value['metadata']['phone_number_id']

            contacts = value.get('contacts', [])
            contact_name = contacts[0].get('profile', {}).get('name', '') if contacts else ''

            channel_provider = ChannelProvider.objects.filter(phone_number_id=phone_number_id).first()
            if not channel_provider or not channel_provider.organization:
                return Response({'detail': 'Channel not found.'}, status=404)

            org = channel_provider.organization

            # ── Mídia recebida (imagem, documento, áudio, vídeo) ──────────────
            MEDIA_TYPES = {'image', 'document', 'audio', 'video', 'sticker'}
            if msg_type in MEDIA_TYPES:
                return self._handle_incoming_media(
                    org=org, from_phone=from_phone, msg=msg,
                    msg_type=msg_type, channel_provider=channel_provider, contact_name=contact_name,
                )

            # ── Texto ─────────────────────────────────────────────────────────
            if msg_type != 'text':
                return Response({'received': True, 'note': f'type {msg_type} ignored'}, status=200)

            text = msg['text']['body'].strip()

        except (KeyError, IndexError) as e:
            import logging
            logging.getLogger('apps').error(f'Webhook Meta payload error: {e} | data: {data}')
            return Response({'received': True}, status=200)

        return self._process_message(
            org=org, sender_id=from_phone, text=text,
            channel='whatsapp', channel_provider=channel_provider, contact_name=contact_name,
        )

    def _handle_status_update(self, statuses):
        """Atualiza msg_status das mensagens OUT conforme notificações do Meta."""
        import logging
        logger = logging.getLogger('apps')

        STATUS_MAP = {
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
        }

        for status_obj in statuses:
            wamid = status_obj.get('id')
            new_status = STATUS_MAP.get(status_obj.get('status'))
            if not wamid or not new_status:
                continue
            updated = Message.objects.filter(
                provider_message_id=wamid,
                direction='OUT',
            ).update(msg_status=new_status)
            if updated:
                logger.info(f'Status atualizado: wamid={wamid} → {new_status}')

        return Response({'received': True}, status=200)

    def _handle_incoming_media(self, org, from_phone, msg, msg_type, channel_provider, contact_name=''):
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
        if media_id and channel_provider.access_token:
            try:
                # 1. Obtém a URL de download temporária do Meta
                meta_resp = http_requests.get(
                    f'https://graph.facebook.com/v22.0/{media_id}',
                    headers={'Authorization': f'Bearer {channel_provider.access_token}'},
                    timeout=10,
                )
                if meta_resp.status_code == 200:
                    download_url = meta_resp.json().get('url', '')
                    if download_url:
                        # 2. Baixa o arquivo com o token
                        dl_resp = http_requests.get(
                            download_url,
                            headers={'Authorization': f'Bearer {channel_provider.access_token}'},
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
            lead=lead, channel='whatsapp',
            defaults={'organization': org, 'state': 'active'},
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
        sender_id = data.get('from_phone', '') or data.get('sender_id', '')
        text = data.get('text', '').strip()
        channel = (data.get('provider', 'WHATSAPP') or 'WHATSAPP').lower()

        try:
            org = Organization.objects.get(api_key=org_key)
        except Organization.DoesNotExist:
            return Response({'detail': 'Organization not found.'}, status=404)

        return self._process_message(org=org, sender_id=sender_id, text=text, channel=channel)

    def _process_message(self, org, sender_id, text, channel='whatsapp', channel_provider=None, contact_name=''):
        """Lógica comum: cria/atualiza lead, roda QualifierEngine, salva e envia mensagens."""
        from django.utils import timezone

        # ── Resolve o lead pelo identificador do canal ─────────────────────────
        if channel in ('messenger', 'facebook'):
            lead, created = Lead.objects.get_or_create(
                organization=org,
                facebook_psid=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                    'phone': '',
                }
            )
        elif channel == 'instagram':
            lead, created = Lead.objects.get_or_create(
                organization=org,
                instagram_user_id=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                    'phone': '',
                }
            )
        else:  # whatsapp
            lead, created = Lead.objects.get_or_create(
                organization=org,
                phone=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                }
            )

        if not created and contact_name and not lead.full_name:
            lead.full_name = contact_name
            lead.save(update_fields=['full_name'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel=channel,
            defaults={'organization': org, 'state': 'active', 'last_message_at': timezone.now()},
        )
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())

        Message.objects.create(
            conversation=conv, organization=org, direction='IN', text=text,
        )

        if not lead.is_ai_active:
            return Response({'received': True, 'replies': [], 'lead': _lead_summary(lead)})

        engine = QualifierEngine(lead)
        replies = engine.process_message(text)

        # Usa o channel_provider já resolvido ou busca no banco como fallback
        if channel_provider is None:
            channel_provider = ChannelProvider.objects.filter(
                organization=org, provider=channel, is_active=True,
            ).first()

        reply_texts = []
        for reply in replies:
            is_media = isinstance(reply, dict)
            caption = reply.get('caption', '') if is_media else ''
            db_text = caption if caption else (f"[{reply.get('type', 'mídia')}]" if is_media else reply)

            Message.objects.create(
                conversation=conv, organization=org, direction='OUT', text=db_text,
            )
            reply_texts.append(db_text)

            if not channel_provider or not channel_provider.access_token:
                continue

            if channel in ('messenger', 'facebook'):
                if not is_media:
                    _send_facebook_message(
                        page_id=channel_provider.page_id,
                        access_token=channel_provider.access_token,
                        recipient_id=sender_id,
                        text=reply,
                    )
            elif channel == 'instagram':
                if not is_media:
                    _send_instagram_message(
                        instagram_account_id=channel_provider.instagram_account_id,
                        access_token=channel_provider.access_token,
                        recipient_id=sender_id,
                        text=reply,
                    )
            else:  # whatsapp
                if channel_provider.phone_number_id:
                    if is_media:
                        _send_whatsapp_media(
                            phone_number_id=channel_provider.phone_number_id,
                            access_token=channel_provider.access_token,
                            to=sender_id,
                            media_type=reply.get('type', 'video'),
                            url=reply['url'],
                            caption=caption,
                        )
                        import time
                        delay = 7 if reply.get('type') == 'video' else 4
                        time.sleep(delay)
                    else:
                        _send_whatsapp_message(
                            phone_number_id=channel_provider.phone_number_id,
                            access_token=channel_provider.access_token,
                            to=sender_id,
                            text=reply,
                        )

        return Response({'received': True, 'replies': reply_texts, 'lead': _lead_summary(lead)})


class MetaWebhookView(APIView):
    """Webhook unificado para Facebook Page/Messenger e Instagram (DMs e Comments)."""
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
        obj = data.get('object', '')

        if obj == 'page':
            return self._handle_page_payload(data)
        elif obj == 'instagram':
            return self._handle_instagram_payload(data)
        else:
            logger.warning(f'MetaWebhook: object desconhecido = {obj!r}')
            return Response({'received': True}, status=200)

    # ── Facebook Page / Messenger ──────────────────────────────────────────────

    def _handle_page_payload(self, data):
        """Processa mensagens de Facebook Page e Messenger (object == 'page')."""
        try:
            for entry in data.get('entry', []):
                for messaging in entry.get('messaging', []):
                    sender_id = messaging.get('sender', {}).get('id', '')
                    recipient_id = messaging.get('recipient', {}).get('id', '')
                    message = messaging.get('message', {})

                    # Ignora echo (mensagens enviadas pela própria página)
                    if message.get('is_echo'):
                        continue

                    text = message.get('text', '').strip()
                    if not text:
                        continue

                    channel_provider = ChannelProvider.objects.filter(
                        page_id=recipient_id, is_active=True,
                    ).first()
                    if not channel_provider or not channel_provider.organization:
                        logger.warning(f'MetaWebhook Page: page_id={recipient_id!r} não encontrado.')
                        continue

                    org = channel_provider.organization
                    contact_name = (
                        messaging.get('sender', {}).get('name', '')
                        or _fetch_messenger_name(sender_id, recipient_id, channel_provider.access_token)
                    )

                    self._process_message(
                        org=org, sender_id=sender_id, text=text,
                        channel='messenger', channel_provider=channel_provider,
                        contact_name=contact_name,
                    )

        except Exception as e:
            logger.error(f'MetaWebhook Page error: {e}')

        return Response({'received': True}, status=200)

    # ── Instagram DMs e Comments ───────────────────────────────────────────────

    def _handle_instagram_payload(self, data):
        """Processa DMs e Comments do Instagram (object == 'instagram')."""
        try:
            for entry in data.get('entry', []):
                # DMs: entry.messaging[]
                for messaging in entry.get('messaging', []):
                    sender_id = messaging.get('sender', {}).get('id', '')
                    recipient_id = messaging.get('recipient', {}).get('id', '')
                    message = messaging.get('message', {})

                    if message.get('is_echo'):
                        continue

                    text = message.get('text', '').strip()
                    if not text:
                        continue

                    channel_provider = ChannelProvider.objects.filter(
                        instagram_account_id=recipient_id, is_active=True,
                    ).first()
                    if not channel_provider or not channel_provider.organization:
                        logger.warning(f'MetaWebhook IG: instagram_account_id={recipient_id!r} não encontrado.')
                        continue

                    org = channel_provider.organization
                    contact_name = _fetch_instagram_name(sender_id, channel_provider.access_token)
                    self._process_message(
                        org=org, sender_id=sender_id, text=text,
                        channel='instagram', channel_provider=channel_provider,
                        contact_name=contact_name,
                    )

                # Comments: entry.changes[].field == 'comments'
                for change in entry.get('changes', []):
                    if change.get('field') != 'comments':
                        continue
                    self._handle_instagram_comment(data=change.get('value', {}), entry=entry)

        except Exception as e:
            logger.error(f'MetaWebhook Instagram error: {e}')

        return Response({'received': True}, status=200)

    def _handle_instagram_comment(self, data, entry):
        """Captura comentário do Instagram, salva como IN e gera sugestão de resposta."""
        from django.utils import timezone

        comment_id = data.get('id', '')
        text = data.get('text', '').strip()
        sender = data.get('from', {})
        sender_id = sender.get('id', '')
        sender_name = sender.get('name', '')
        media_id = data.get('media', {}).get('id', '')

        if not text or not sender_id:
            return

        # Identifica a conta Instagram pelo recipient_id do entry (se disponível)
        recipient_id = entry.get('id', '')
        channel_provider = ChannelProvider.objects.filter(
            instagram_account_id=recipient_id, is_active=True,
        ).first()
        if not channel_provider or not channel_provider.organization:
            logger.warning(f'MetaWebhook IG comment: instagram_account_id={recipient_id!r} não encontrado.')
            return

        org = channel_provider.organization

        lead, _ = Lead.objects.get_or_create(
            organization=org,
            instagram_user_id=sender_id,
            defaults={
                'status': 'NEW', 'source': 'INSTAGRAM_AD', 'channels_used': 'instagram',
                'conversation_state': 'initial', 'full_name': sender_name or '',
                'phone': '',
            }
        )

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel='instagram',
            defaults={'organization': org, 'state': 'active', 'last_message_at': timezone.now()},
        )
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=timezone.now())

        # Salva o comentário como mensagem IN com prefixo para diferenciar no painel
        msg_text = f'[Comentário] {text}'
        Message.objects.create(
            conversation=conv, organization=org, direction='IN',
            text=msg_text, provider_message_id=comment_id,
        )
        logger.info(f'IG comment captured from {sender_id}: {text[:60]}')

        # Gera sugestão de resposta via IA (nunca funil de vendas — usa RAG ou GPT direto)
        if lead.is_ai_active:
            suggestion = _generate_comment_suggestion(org=org, lead=lead, comment_text=text)
            if suggestion:
                Message.objects.create(
                    conversation=conv, organization=org, direction='OUT',
                    text=f'[Sugestão] {suggestion}', msg_status='sent',
                )

    # ── Herda _process_message do WhatsAppWebhookView via mixin-like delegation ─

    def _process_message(self, org, sender_id, text, channel='whatsapp', channel_provider=None, contact_name=''):
        return WhatsAppWebhookView._process_message(
            self, org=org, sender_id=sender_id, text=text,
            channel=channel, channel_provider=channel_provider, contact_name=contact_name,
        )


def _send_facebook_message(page_id, access_token, recipient_id, text):
    """Envia mensagem de texto via Messenger/Facebook Page API."""
    import requests as http_requests
    logger = logging.getLogger('apps')

    url = f'https://graph.facebook.com/v22.0/me/messages'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text},
        'messaging_type': 'RESPONSE',
    }
    try:
        resp = http_requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            params={'access_token': access_token},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f'Facebook send error: {resp.status_code} {resp.text}')
            return None
        mid = resp.json().get('message_id')
        logger.info(f'Facebook message sent to {recipient_id}: {text[:50]} | mid={mid}')
        return mid
    except Exception as e:
        logger.error(f'Facebook send exception: {e}')
        return None


COMMENT_SYSTEM_PROMPT = """\
Você é o community manager do perfil @bordercolliesul no Instagram.
Sua função é sugerir respostas humanizadas, calorosas e breves para comentários de seguidores.

REGRAS ABSOLUTAS:
1. NUNCA use roteiros de vendas, funil de qualificação ou pergunte sobre orçamento em comentários.
2. Se o comentário for um elogio → responda com carinho, gratidão e um emoji pertinente.
3. Se for uma dúvida sobre a raça → responda de forma informativa e amigável (1-2 frases).
4. Se demonstrar interesse em adquirir um filhote → convide gentilmente para o direct ou WhatsApp.
   Exemplo: "Que bom! 🐾 Nos chama no direct ou no WhatsApp que a gente te conta tudo com carinho!"
5. Respostas curtas: máximo 2-3 frases. Adequado para um comentário público do Instagram.
6. Tom informal, caloroso — como um amigo especialista respondendo fãs da raça.

Responda APENAS com o texto da sugestão, sem aspas nem prefixos."""


def _generate_comment_suggestion(org, lead, comment_text: str) -> str | None:
    """Gera sugestão de resposta para comentário do Instagram usando RAG ou GPT direto."""
    logger = logging.getLogger('apps')
    try:
        from apps.core.models import AgentConfig
        from apps.rag.services.rag_service import RAGService

        cfg = AgentConfig.objects.filter(organization=org).first()
        if cfg and cfg.is_ready():
            # Tenta via RAG com prompt específico para comentários
            rag = RAGService(cfg)
            kb_results = []
            conv_results = []
            try:
                from apps.rag.services.embedding_service import EmbeddingService
                emb = EmbeddingService(cfg).embed(comment_text)
                if emb:
                    kb_results = rag._search_knowledge_base(emb, org.id)
            except Exception:
                pass

            msgs = rag._build_messages(
                system_prompt=COMMENT_SYSTEM_PROMPT,
                kb_results=kb_results,
                conv_results=conv_results,
                history=[],
                current_message=comment_text,
            )
            suggestion = rag._generate(msgs)
            if suggestion:
                return suggestion

        # Fallback: GPT direto sem RAG
        from django.conf import settings
        from openai import OpenAI
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if cfg and cfg.openai_api_key:
            api_key = cfg.openai_api_key
        if not api_key:
            return None

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': COMMENT_SYSTEM_PROMPT},
                {'role': 'user', 'content': comment_text},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f'_generate_comment_suggestion error: {e}')
        return None


def _fetch_instagram_name(sender_id, access_token):
    """Busca o nome/username do usuário do Instagram via Graph API."""
    import requests as http_requests
    try:
        resp = http_requests.get(
            f'https://graph.instagram.com/v22.0/{sender_id}',
            params={'fields': 'name,username', 'access_token': access_token},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('name') or data.get('username') or ''
    except Exception:
        pass
    return ''


def _fetch_messenger_name(sender_id, page_id, access_token):
    """Busca o nome do usuário do Messenger via Graph API."""
    import requests as http_requests
    try:
        resp = http_requests.get(
            f'https://graph.facebook.com/v22.0/{sender_id}',
            params={'fields': 'name,first_name,last_name', 'access_token': access_token},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('name') or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or ''
    except Exception:
        pass
    return ''


def _send_instagram_message(instagram_account_id, access_token, recipient_id, text):
    """Envia DM de texto via Instagram Graph API."""
    import requests as http_requests
    logger = logging.getLogger('apps')

    url = f'https://graph.instagram.com/v22.0/{instagram_account_id}/messages'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text},
        'messaging_type': 'RESPONSE',
    }
    try:
        resp = http_requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f'Instagram DM send error: {resp.status_code} {resp.text}')
            return None
        mid = resp.json().get('message_id')
        logger.info(f'Instagram DM sent to {recipient_id}: {text[:50]} | mid={mid}')
        return mid
    except Exception as e:
        logger.error(f'Instagram DM send exception: {e}')
        return None


def _send_whatsapp_message(phone_number_id, access_token, to, text):
    """Envia mensagem de texto via WhatsApp Cloud API. Retorna wamid ou None."""
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
            return None
        data = resp.json()
        wamid = data.get('messages', [{}])[0].get('id')
        logger.info(f'WhatsApp message sent to {to}: {text[:50]} | wamid={wamid}')
        return wamid
    except Exception as e:
        logger.error(f'WhatsApp send exception: {e}')
        return None


def _send_whatsapp_media(phone_number_id, access_token, to, media_type, url, caption=''):
    """Envia vídeo ou imagem via WhatsApp Cloud API usando link público."""
    import requests as http_requests
    import logging
    logger = logging.getLogger('apps')

    send_url = f'https://graph.facebook.com/v22.0/{phone_number_id}/messages'
    media_key = 'video' if media_type == 'video' else 'image'
    media_body = {'link': url}
    if caption:
        media_body['caption'] = caption
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': media_key,
        media_key: media_body,
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

class QuickReplyCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = QuickReplyCategorySerializer

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return QuickReplyCategory.objects.none()
        return QuickReplyCategory.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)


class QuickReplyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = QuickReplySerializer

    def get_queryset(self):
        from django.db.models import Q
        org = _get_org(self.request.user)
        if not org:
            return QuickReply.objects.none()
        # Tenant-level replies (user IS NULL) + personal replies (user = requester)
        return (
            QuickReply.objects
            .filter(organization=org, is_active=True)
            .filter(Q(user__isnull=True) | Q(user=self.request.user))
            .select_related('category_ref')
            .order_by('sort_order', 'title', 'shortcut')
        )

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


# ─── Agent Config ──────────────────────────────────────────────────────────────

class AgentConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        cfg, _ = AgentConfig.objects.get_or_create(organization=org)
        return Response(AgentConfigSerializer(cfg).data)

    def put(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        cfg, _ = AgentConfig.objects.get_or_create(organization=org)
        serializer = AgentConfigSerializer(cfg, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AgentConfigSerializer(cfg).data)
        return Response(serializer.errors, status=400)


# ─── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        from apps.rag.services.training_service import list_knowledge_base
        entries = list_knowledge_base(org.id)
        return Response(entries)

    def post(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        title = request.data.get('title', '').strip()
        content = request.data.get('content', '').strip()
        if not title or not content:
            return Response({'detail': 'title e content são obrigatórios.'}, status=400)
        try:
            cfg = org.agent_config
        except AgentConfig.DoesNotExist:
            return Response({'detail': 'Configure a chave OpenAI antes de adicionar entradas.'}, status=400)
        if not cfg.openai_api_key:
            return Response({'detail': 'Chave OpenAI não configurada.'}, status=400)
        try:
            from apps.rag.services.training_service import add_knowledge_base_entry
            entry = add_knowledge_base_entry(cfg, title, content)
            return Response(entry, status=201)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        except Exception as e:
            logger.error(f'KnowledgeBaseView.post error: {e}')
            return Response({'detail': 'Erro ao adicionar entrada.'}, status=500)


class KnowledgeBaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, entry_id):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        from apps.rag.services.training_service import delete_knowledge_base_entry
        delete_knowledge_base_entry(org.id, entry_id)
        return Response(status=204)


# ─── Initial Message Media ────────────────────────────────────────────────────

class InitialMessageMediaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        cfg, _ = AgentConfig.objects.get_or_create(organization=org)
        media = cfg.initial_media.all()
        return Response(InitialMessageMediaSerializer(media, many=True, context={'request': request}).data)

    def post(self, request):
        import mimetypes
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        cfg, _ = AgentConfig.objects.get_or_create(organization=org)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'Arquivo obrigatório.'}, status=400)

        mime = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or ''
        if mime.startswith('video/'):
            media_type = 'video'
        elif mime.startswith('image/'):
            media_type = 'image'
        else:
            return Response({'detail': 'Apenas imagens e vídeos são permitidos.'}, status=400)

        order = cfg.initial_media.count()
        obj = InitialMessageMedia.objects.create(
            agent_config=cfg,
            file=uploaded,
            media_type=media_type,
            original_name=uploaded.name,
            order=order,
        )
        return Response(
            InitialMessageMediaSerializer(obj, context={'request': request}).data,
            status=201,
        )


class InitialMessageMediaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, media_id):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        try:
            cfg = org.agent_config
            obj = cfg.initial_media.get(pk=media_id)
        except (AgentConfig.DoesNotExist, InitialMessageMedia.DoesNotExist):
            return Response({'detail': 'Não encontrado.'}, status=404)
        obj.file.delete(save=False)
        obj.delete()
        return Response(status=204)


# ─── Training Data Export ──────────────────────────────────────────────────────

class TrainingDataExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'No organization.'}, status=404)
        from apps.rag.services.training_service import export_training_jsonl
        from django.http import HttpResponse
        jsonl_content = export_training_jsonl(org.id)
        response = HttpResponse(jsonl_content, content_type='application/jsonl')
        response['Content-Disposition'] = f'attachment; filename="training_data_org{org.id}.jsonl"'
        return response
