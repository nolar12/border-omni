import logging
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import OuterRef, Subquery, Case, When, Value, IntegerField, BooleanField, Q, F
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Organization, UserProfile, Plan, Subscription, AgentConfig, InitialMessageMedia, GalleryMedia
from apps.leads.models import Lead, Note
from apps.conversations.models import Conversation, Message, MessageTemplate
from apps.quick_replies.models import QuickReply, QuickReplyCategory
from apps.channels.models import ChannelProvider
from apps.qualifier.engine import QualifierEngine

from api.serializers import (
    UserSerializer, LeadListSerializer, LeadDetailSerializer,
    MessageSerializer, NoteSerializer,
    QuickReplySerializer, QuickReplyCategorySerializer,
    ChannelProviderSerializer, PlanSerializer, SubscriptionSerializer,
    AgentConfigSerializer, InitialMessageMediaSerializer,
    MessageTemplateSerializer, GalleryMediaSerializer,
    ContractSerializer, ContractPublicSerializer,
    GenericNoteSerializer,
    DogListSerializer, DogDetailSerializer,
    LitterListSerializer, LitterDetailSerializer,
    DogHealthRecordSerializer, LitterHealthRecordSerializer,
    DogMediaSerializer, LitterMediaSerializer,
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
                u = User.objects.filter(email=email).first()
                if u:
                    user = authenticate(request, username=u.username, password=password)
            except Exception:
                pass
        if not user:
            return Response({'detail': 'Credenciais inválidas.'}, status=401)
        return Response(_get_tokens(user))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        data = request.data

        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        user.save(update_fields=['first_name', 'last_name'])

        if 'phone' in data:
            try:
                profile = user.profile
                profile.phone = data['phone']
                profile.save(update_fields=['phone'])
            except Exception:
                pass

        return Response(UserSerializer(user).data)


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
        qs = Lead.objects.filter(organization=org).select_related('assigned_to').prefetch_related('tags')
        show_archived = self.request.query_params.get('is_archived', 'false').lower()
        if show_archived == 'true':
            qs = qs.filter(is_archived=True)
        else:
            qs = qs.filter(is_archived=False)
        lead_classification = self.request.query_params.get('lead_classification')
        if lead_classification:
            qs = qs.filter(lead_classification=lead_classification)

        # Ordena pela última atividade de mensagem em qualquer conversa do lead.
        # Qualquer mensagem (IN ou OUT, humana ou bot) move o lead para o topo.
        # Leads sem conversa ficam no final, ordenados por created_at desc.
        last_msg_ts_sq = Subquery(
            Conversation.objects.filter(
                lead=OuterRef('pk'),
            ).order_by('-last_message_at').values('last_message_at')[:1]
        )

        qs = qs.annotate(
            _last_msg_ts=last_msg_ts_sq,
        ).order_by(
            F('_last_msg_ts').desc(nulls_last=True),
            '-created_at',
        )

        return qs

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
        """Gera 3 sugestões de resposta para o atendente usando a persona Border Collie Sul."""
        lead = self.get_object()
        org = lead.organization
        message_text = request.data.get('message', '').strip()
        channel = request.data.get('channel', 'whatsapp')
        brief = request.data.get('brief', '').strip()  # contexto adicional do atendente

        if not message_text:
            return Response({'suggestions': []})

        try:
            agent_config = org.agent_config
        except AgentConfig.DoesNotExist:
            return Response({'suggestions': []})

        if not agent_config.openai_api_key:
            return Response({'suggestions': []})

        # Busca a conversa ativa para a lógica de saudação
        conv = Conversation.objects.filter(lead=lead, channel=channel).first()

        # Apenas o primeiro nome do atendente para a saudação
        user = request.user
        agent_name = (
            user.first_name.strip()
            or user.get_full_name().strip().split()[0]
            if (user.first_name or user.get_full_name())
            else user.username
        )

        try:
            from apps.rag.services.rag_service import RAGService
            suggestions = RAGService(agent_config).suggest_three_options(
                lead, message_text, conv=conv, brief=brief, agent_name=agent_name
            )
        except Exception as e:
            logger.exception(f'suggest_response error: {e}')
            suggestions = []

        return Response({'suggestions': suggestions})

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
        is_audio = mime_type.startswith('audio/')
        is_video = mime_type.startswith('video/')

        file_bytes = uploaded.read()
        file_name = uploaded.name

        # WhatsApp voice: converte todo áudio para OGG/opus via ffmpeg
        # (formato nativo do WhatsApp — audio/mp4 e audio/webm causam falha na entrega)
        if is_audio and 'ogg' not in mime_type:
            import subprocess as _sp
            import tempfile as _tf
            import os as _os
            in_ext = os.path.splitext(file_name)[1] or '.bin'
            tmp_in = _tf.NamedTemporaryFile(suffix=in_ext, delete=False)
            tmp_out_path = tmp_in.name.rsplit('.', 1)[0] + '.ogg'
            try:
                tmp_in.write(file_bytes)
                tmp_in.close()
                result = _sp.run(
                    ['ffmpeg', '-y', '-i', tmp_in.name, '-c:a', 'libopus', '-b:a', '64k', tmp_out_path],
                    capture_output=True, timeout=30,
                )
                if result.returncode == 0:
                    with open(tmp_out_path, 'rb') as f:
                        file_bytes = f.read()
                    mime_type = 'audio/ogg'
                    base = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                    file_name = f'{base}.ogg'
                    logger.info(f'Audio converted to OGG/opus: {file_name} ({len(file_bytes)} bytes)')
                else:
                    logger.warning(f'ffmpeg conversion failed: {result.stderr.decode()[:500]}')
                    return Response({'detail': 'Não foi possível converter o áudio.'}, status=500)
            except FileNotFoundError:
                return Response({'detail': 'ffmpeg não encontrado no servidor.'}, status=500)
            except Exception as conv_err:
                logger.warning(f'Audio conversion error: {conv_err}')
                return Response({'detail': f'Erro ao converter áudio: {conv_err}'}, status=500)
            finally:
                try: _os.unlink(tmp_in.name)
                except OSError: pass
                try: _os.unlink(tmp_out_path)
                except OSError: pass

        # 1. Faz upload da mídia para o Meta e obtém media_id
        upload_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/media'
        try:
            upload_resp = http_requests.post(
                upload_url,
                headers={'Authorization': f'Bearer {channel_provider.access_token}'},
                files={'file': (file_name, file_bytes, mime_type)},
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
        elif is_audio:
            media_payload = {
                'messaging_product': 'whatsapp',
                'to': lead.phone,
                'type': 'audio',
                'audio': {'id': media_id},
            }
        elif is_video:
            media_payload = {
                'messaging_product': 'whatsapp',
                'to': lead.phone,
                'type': 'video',
                'video': {'id': media_id, 'caption': caption},
            }
        else:
            media_payload = {
                'messaging_product': 'whatsapp',
                'to': lead.phone,
                'type': 'document',
                'document': {'id': media_id, 'caption': caption, 'filename': file_name},
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
        if is_audio:
            msg_text = f'🎵 {file_name}'
        elif is_video:
            msg_text = f'🎥 {file_name}' + (f' — {caption}' if caption else '')
        elif is_image:
            msg_text = f'🖼 {file_name}' + (f' — {caption}' if caption else '')
        else:
            msg_text = f'📎 {file_name}' + (f' — {caption}' if caption else '')
        wamid_file = send_resp.json().get('messages', [{}])[0].get('id')
        msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=msg_text,
            provider_message_id=wamid_file,
            msg_status='sent',
        )
        logger.info(f'File sent to {lead.phone}: {file_name} | mime={mime_type} | wamid={wamid_file}')
        return Response(MessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'], url_path='send_gallery_item')
    def send_gallery_item(self, request, pk=None):
        """Envia um item da galeria (imagem ou vídeo) via WhatsApp para o lead, usando link público."""
        import requests as http_requests

        lead = self.get_object()
        org = lead.organization
        gallery_media_id = request.data.get('gallery_media_id')
        caption = request.data.get('caption', '').strip()

        if not gallery_media_id:
            return Response({'detail': 'gallery_media_id obrigatório.'}, status=400)

        try:
            item = GalleryMedia.objects.get(pk=gallery_media_id, organization=org)
        except GalleryMedia.DoesNotExist:
            return Response({'detail': 'Item de galeria não encontrado.'}, status=404)

        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider='whatsapp', is_active=True,
        ).first()
        if not channel_provider or not channel_provider.access_token or not channel_provider.phone_number_id:
            return Response({'detail': 'Canal WhatsApp não configurado.'}, status=400)

        msg_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/messages'
        media_type_lower = item.media_type.lower()

        import mimetypes as _mimetypes
        from pathlib import Path
        from django.conf import settings as django_settings

        # Resolve the file on disk from the stored relative path (/media/...).
        # file_url examples: "/media/gallery/3/abc123.jpg" or legacy absolute URL.
        if item.file_url.startswith('/media/'):
            rel_path = item.file_url[len('/media/'):]
        elif '/media/' in item.file_url:
            rel_path = item.file_url.split('/media/', 1)[1]
        else:
            rel_path = None

        file_on_disk = Path(django_settings.MEDIA_ROOT) / rel_path if rel_path else None

        wa_headers_json = {
            'Authorization': f'Bearer {channel_provider.access_token}',
            'Content-Type': 'application/json',
        }

        # Upload the file to WhatsApp Media API to get a media_id.
        # This avoids any dependency on a public URL / ngrok being active.
        media_id = None
        if file_on_disk and file_on_disk.exists():
            try:
                mime = item.mime_type or _mimetypes.guess_type(str(file_on_disk))[0] or 'application/octet-stream'
                upload_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/media'
                with open(file_on_disk, 'rb') as fh:
                    upload_resp = http_requests.post(
                        upload_url,
                        headers={'Authorization': f'Bearer {channel_provider.access_token}'},
                        data={'messaging_product': 'whatsapp'},
                        files={'file': (file_on_disk.name, fh, mime)},
                        timeout=60,
                    )
                if upload_resp.status_code == 200:
                    media_id = upload_resp.json().get('id')
                else:
                    logger.warning(f'WA media upload failed: {upload_resp.status_code} {upload_resp.text}')
            except Exception as e:
                logger.warning(f'WA media upload error: {e}')

        # Build the send-message payload: prefer media_id (no public URL needed),
        # fall back to link (requires ngrok/public host) if upload failed.
        if media_id:
            media_ref = {'id': media_id}
        else:
            # Fallback: reconstruct public URL (requires ngrok to be active).
            _media_base = (django_settings.MEDIA_BASE_URL or '').rstrip('/')
            if item.file_url.startswith('http'):
                public_file_url = item.file_url
            elif _media_base:
                public_file_url = f'{_media_base}{item.file_url}'
            else:
                public_file_url = request.build_absolute_uri(item.file_url)
            media_ref = {'link': public_file_url}
            logger.warning('Gallery: using link fallback (media upload failed). Requires public URL to be reachable.')

        media_type_key = 'image' if item.media_type == 'IMAGE' else 'video'
        # Send media WITHOUT caption — description follows as a separate text message.
        media_payload = {
            'messaging_product': 'whatsapp',
            'to': lead.phone,
            'type': media_type_key,
            media_type_key: media_ref,
        }

        try:
            resp = http_requests.post(msg_url, json=media_payload, headers=wa_headers_json, timeout=20)
            if resp.status_code != 200:
                logger.error(f'Gallery send error: {resp.status_code} {resp.text}')
                return Response({'detail': f'Erro ao enviar mídia: {resp.text}'}, status=502)
        except Exception as e:
            return Response({'detail': f'Erro ao enviar item de galeria: {str(e)}'}, status=500)

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel='whatsapp',
            defaults={'organization': org, 'state': 'active'},
        )

        label = item.name or media_type_lower
        media_label = f'🖼 {label}' if item.media_type == 'IMAGE' else f'▶ {label}'
        wamid = resp.json().get('messages', [{}])[0].get('id', '')
        media_msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=media_label,
            provider_message_id=wamid,
            msg_status='sent',
        )

        saved_messages = [media_msg]

        # If there is a caption, send it as a separate text message.
        if caption:
            try:
                text_payload = {
                    'messaging_product': 'whatsapp',
                    'to': lead.phone,
                    'type': 'text',
                    'text': {'body': caption, 'preview_url': False},
                }
                text_resp = http_requests.post(msg_url, json=text_payload, headers=wa_headers_json, timeout=20)
                text_wamid = ''
                if text_resp.status_code == 200:
                    text_wamid = text_resp.json().get('messages', [{}])[0].get('id', '')
                else:
                    logger.warning(f'Gallery caption text send failed: {text_resp.status_code} {text_resp.text}')
            except Exception as e:
                logger.warning(f'Gallery caption text send error: {e}')
                text_wamid = ''

            text_msg = Message.objects.create(
                conversation=conv,
                organization=org,
                direction='OUT',
                text=caption,
                provider_message_id=text_wamid,
                msg_status='sent',
            )
            saved_messages.append(text_msg)

        return Response({'messages': MessageSerializer(saved_messages, many=True).data}, status=201)

    @action(detail=True, methods=['post'])
    def send_template(self, request, pk=None):
        """Envia template ao lead.

        WhatsApp: envia como HSM aprovado via WhatsApp Cloud API.
        Instagram/Facebook: renderiza o body_text com as variáveis e envia como DM de texto simples,
        pois essas plataformas não suportam templates HSM formais.
        """
        lead = self.get_object()
        org = lead.organization
        template_id = request.data.get('template_id')
        variables = request.data.get('variables', [])
        header_media_url = request.data.get('header_media_url', '')

        if not template_id:
            return Response({'detail': 'template_id obrigatório.'}, status=400)

        try:
            template = MessageTemplate.objects.get(pk=template_id, organization=org)
        except MessageTemplate.DoesNotExist:
            return Response({'detail': 'Template não encontrado.'}, status=404)

        if template.status != 'APPROVED':
            return Response({'detail': f'Template não aprovado (status: {template.status}).'}, status=400)

        # Detecta o canal ativo do lead (conversa mais recente ou fallback por channels_used)
        active_conv = lead.conversations.order_by('-last_message_at').first()
        if active_conv:
            active_channel = active_conv.channel
        else:
            active_channel = (lead.channels_used or 'whatsapp').split(',')[0].strip()

        # ── Instagram ────────────────────────────────────────────────────────────
        if active_channel == 'instagram':
            if not lead.instagram_user_id:
                return Response({'detail': 'Lead Instagram sem ID de usuário.'}, status=400)

            channel_provider = ChannelProvider.objects.filter(
                organization=org, provider='instagram', is_active=True,
            ).first()
            if not channel_provider or not channel_provider.access_token:
                return Response({'detail': 'Canal Instagram não configurado.'}, status=400)

            msg_text = template.body_text
            for i, val in enumerate(variables, start=1):
                msg_text = msg_text.replace(f'{{{{{i}}}}}', str(val))
            if template.header_text:
                msg_text = f'{template.header_text}\n\n{msg_text}'
            if template.footer_text:
                msg_text = f'{msg_text}\n\n{template.footer_text}'

            mid = _send_instagram_message(
                instagram_account_id=channel_provider.instagram_account_id,
                access_token=channel_provider.access_token,
                recipient_id=lead.instagram_user_id,
                text=msg_text,
            )
            provider_msg_id = mid or ''

            conv, _ = Conversation.objects.get_or_create(
                lead=lead, channel='instagram',
                defaults={'organization': org, 'state': 'active'},
            )
            msg = Message.objects.create(
                conversation=conv,
                organization=org,
                direction='OUT',
                text=f'[Template: {template.name}]\n{msg_text}',
                provider_message_id=provider_msg_id,
                msg_status='sent' if mid else 'failed',
            )
            if not mid:
                return Response({'detail': 'Falha ao enviar mensagem Instagram. Verifique logs.'}, status=502)
            return Response(MessageSerializer(msg).data, status=201)

        # ── Facebook / Messenger ─────────────────────────────────────────────────
        if active_channel in ('facebook', 'messenger'):
            if not lead.facebook_psid:
                return Response({'detail': 'Lead Facebook sem PSID.'}, status=400)

            channel_provider = ChannelProvider.objects.filter(
                organization=org, provider__in=['facebook', 'messenger'], is_active=True,
            ).first()
            if not channel_provider or not channel_provider.access_token:
                return Response({'detail': 'Canal Facebook não configurado.'}, status=400)

            msg_text = template.body_text
            for i, val in enumerate(variables, start=1):
                msg_text = msg_text.replace(f'{{{{{i}}}}}', str(val))
            if template.header_text:
                msg_text = f'{template.header_text}\n\n{msg_text}'
            if template.footer_text:
                msg_text = f'{msg_text}\n\n{template.footer_text}'

            mid = _send_facebook_message(
                page_id=channel_provider.page_id,
                access_token=channel_provider.access_token,
                recipient_id=lead.facebook_psid,
                text=msg_text,
            )
            provider_msg_id = mid or ''

            conv, _ = Conversation.objects.get_or_create(
                lead=lead, channel=active_channel,
                defaults={'organization': org, 'state': 'active'},
            )
            msg = Message.objects.create(
                conversation=conv,
                organization=org,
                direction='OUT',
                text=f'[Template: {template.name}]\n{msg_text}',
                provider_message_id=provider_msg_id,
                msg_status='sent' if mid else 'failed',
            )
            if not mid:
                return Response({'detail': 'Falha ao enviar mensagem Facebook. Verifique logs.'}, status=502)
            return Response(MessageSerializer(msg).data, status=201)

        # ── WhatsApp (padrão) ────────────────────────────────────────────────────
        header_type = (template.header_type or 'NONE').upper()
        if header_type in ('IMAGE', 'VIDEO', 'DOCUMENT') and not header_media_url:
            return Response({'detail': f'Este template exige uma URL de {header_type.lower()} (header_media_url).'}, status=400)

        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider='whatsapp', is_active=True,
        ).first()
        if not channel_provider or not channel_provider.access_token or not channel_provider.phone_number_id:
            return Response({'detail': 'Canal WhatsApp não configurado.'}, status=400)

        components = []
        if header_type in ('IMAGE', 'VIDEO', 'DOCUMENT') and header_media_url:
            # If the URL is a local relative path (/media/...), upload to WhatsApp Media
            # API and use media_id — avoids dependency on ngrok/public URL being reachable.
            media_ref = _resolve_whatsapp_media_ref(
                header_media_url, channel_provider, request
            )
            header_key = header_type.lower()
            components.append({'type': 'header', 'parameters': [{'type': header_key, header_key: media_ref}]})

        if variables:
            body_params = [{'type': 'text', 'text': str(v)} for v in variables]
            components.append({'type': 'body', 'parameters': body_params})

        wamid = _send_whatsapp_template(
            phone_number_id=channel_provider.phone_number_id,
            access_token=channel_provider.access_token,
            to=lead.phone,
            template_name=template.name,
            language_code=template.language,
            components=components if components else None,
        )

        if not wamid:
            return Response({'detail': 'Falha ao enviar template. Verifique logs.'}, status=502)

        msg_text = template.body_text
        for i, val in enumerate(variables, start=1):
            msg_text = msg_text.replace(f'{{{{{i}}}}}', str(val))
        media_prefix = f'[{header_type}: {header_media_url}]\n' if header_media_url else ''
        msg_text = f'[Template: {template.name}]\n{media_prefix}{msg_text}'

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel='whatsapp',
            defaults={'organization': org, 'state': 'active'},
        )
        msg = Message.objects.create(
            conversation=conv,
            organization=org,
            direction='OUT',
            text=msg_text,
            provider_message_id=wamid,
            msg_status='sent',
        )
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

    @action(detail=True, methods=['post'])
    def reclassify(self, request, pk=None):
        """Reclassifica o lead com o agente de IA — executa em foreground e retorna resultado."""
        lead = self.get_object()
        org = lead.organization
        try:
            cfg = org.agent_config
            if not getattr(cfg, 'openai_api_key', None):
                return Response({'detail': 'OpenAI não configurado.'}, status=400)
        except Exception:
            return Response({'detail': 'Configuração não encontrada.'}, status=400)
        try:
            from apps.qualifier.ai_classifier import AILeadClassifier
            classifier = AILeadClassifier(lead, cfg)
            result = classifier.classify()
            if result:
                classifier._map_to_db(result)
                lead.refresh_from_db()
                return Response({
                    'lead_classification': lead.lead_classification,
                    'score': lead.score,
                    'nivel_maturidade': result.get('nivel_maturidade'),
                    'probabilidade_conversao': result.get('probabilidade_conversao'),
                    'resumo_intencao': result.get('resumo_intencao'),
                })
            return Response({'detail': 'Sem dados suficientes para classificar.'}, status=200)
        except Exception as e:
            logger.warning(f'reclassify error: {e}')
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def reclassify_all(self, request):
        """Reclassifica todos os leads da organização em background."""
        import threading
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'Organização não encontrada.'}, status=400)
        try:
            cfg = org.agent_config
            if not getattr(cfg, 'openai_api_key', None):
                return Response({'detail': 'OpenAI não configurado.'}, status=400)
        except Exception:
            return Response({'detail': 'Configuração não encontrada.'}, status=400)

        def _run():
            from apps.qualifier.ai_classifier import AILeadClassifier
            leads_qs = Lead.objects.filter(organization=org, is_archived=False)
            for lead in leads_qs.iterator():
                try:
                    classifier = AILeadClassifier(lead, cfg)
                    result = classifier.classify()
                    if result:
                        classifier._map_to_db(result)
                except Exception as e:
                    logger.warning(f'reclassify_all lead {lead.pk}: {e}')

        threading.Thread(target=_run, daemon=True).start()
        total = Lead.objects.filter(organization=org, is_archived=False).count()
        return Response({'detail': f'Classificação iniciada para {total} leads em background.'})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        lead = self.get_object()
        lead.is_archived = True
        lead.save(update_fields=['is_archived'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        lead = self.get_object()
        lead.is_archived = False
        lead.save(update_fields=['is_archived'])
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
            field = changes.get('field', '')
            value = changes['value']

            # ── Aprovação / rejeição de template ─────────────────────────────
            if field == 'message_template_status_update':
                return self._handle_template_status_update(value)

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
                if new_status == 'failed':
                    errors = status_obj.get('errors', [])
                    err_detail = '; '.join(
                        f"code={e.get('code')} title={e.get('title')} details={e.get('error_data',{}).get('details','')}"
                        for e in errors
                    ) or 'sem detalhes'
                    logger.error(f'Message FAILED: wamid={wamid} | {err_detail}')
                else:
                    logger.info(f'Status atualizado: wamid={wamid} → {new_status}')

        return Response({'received': True}, status=200)

    def _handle_template_status_update(self, value):
        """Atualiza automaticamente o status de um template quando a Meta aprova ou rejeita."""
        STATUS_MAP = {
            'APPROVED': 'APPROVED',
            'REJECTED': 'REJECTED',
            'PENDING':  'PENDING',
            'PAUSED':   'PAUSED',
            'DISABLED': 'DISABLED',
        }

        meta_id = str(value.get('message_template_id', ''))
        meta_name = value.get('message_template_name', '')
        new_status_raw = str(value.get('event', '')).upper()
        rejection_reason = value.get('reason', '')

        new_status = STATUS_MAP.get(new_status_raw)
        if not new_status:
            logger.info(f'Template webhook: evento desconhecido {new_status_raw!r}, ignorando.')
            return Response({'received': True}, status=200)

        # Tenta localizar pelo meta_template_id primeiro, depois pelo nome
        template = None
        if meta_id:
            template = MessageTemplate.objects.filter(meta_template_id=meta_id).first()
        if not template and meta_name:
            template = MessageTemplate.objects.filter(name=meta_name).first()

        if template:
            template.status = new_status
            template.rejection_reason = rejection_reason or ''
            template.save(update_fields=['status', 'rejection_reason'])
            logger.info(
                f'Template "{template.name}" atualizado via webhook: {new_status}'
                + (f' — motivo: {rejection_reason}' if rejection_reason else '')
            )
        else:
            logger.warning(f'Template webhook: template id={meta_id!r} name={meta_name!r} não encontrado no banco.')

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
                            # 3. Determina extensão — mapa explícito para tipos do WhatsApp
                            # (mimetypes.guess_extension é instável no Debian slim)
                            _MIME_EXT = {
                                'audio/ogg': '.ogg', 'audio/opus': '.ogg',
                                'audio/mpeg': '.mp3', 'audio/mp3': '.mp3',
                                'audio/mp4': '.m4a', 'audio/aac': '.aac',
                                'audio/amr': '.amr', 'audio/webm': '.webm',
                                'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                                'image/png': '.png', 'image/webp': '.webp',
                                'image/gif': '.gif', 'image/heic': '.heic',
                                'video/mp4': '.mp4', 'video/3gpp': '.3gp',
                                'video/quicktime': '.mov',
                                'application/pdf': '.pdf',
                            }
                            base_mime = mime_type.split(';')[0].strip().lower()
                            ext = _MIME_EXT.get(base_mime) or (mimetypes.guess_extension(base_mime) or '')
                            if ext == '.jpe': ext = '.jpg'
                            if ext == '.oga': ext = '.ogg'
                            logger.info(f'Incoming media mime={mime_type!r} → ext={ext!r} filename={filename!r}')
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
        if not created and lead.is_archived:
            fields_to_update = ['is_archived']
            lead.is_archived = False
            if contact_name and not lead.full_name:
                lead.full_name = contact_name
                fields_to_update.append('full_name')
            lead.save(update_fields=fields_to_update)
        elif not created and contact_name and not lead.full_name:
            lead.full_name = contact_name
            lead.save(update_fields=['full_name'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel='whatsapp',
            defaults={'organization': org, 'state': 'active'},
        )
        now = timezone.now()
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=now)
        Lead.objects.filter(pk=lead.pk).update(updated_at=now)

        Message.objects.create(
            conversation=conv,
            organization=org,
            direction='IN',
            text=text,
            provider_message_id=media_id,
        )
        logger.info(f'Incoming [{msg_type}] from {from_phone}: {label or media_id}')

        _notify_users_via_whatsapp(org=org, lead=lead, text=text, channel_provider=channel_provider)

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

        # Verifica se o bot está habilitado globalmente para a organização
        try:
            bot_active = org.agent_config.bot_enabled
        except AgentConfig.DoesNotExist:
            bot_active = True

        # ── Resolve o lead pelo identificador do canal ─────────────────────────
        if channel in ('messenger', 'facebook'):
            lead, created = Lead.objects.get_or_create(
                organization=org,
                facebook_psid=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                    'phone': '', 'is_ai_active': bot_active,
                }
            )
        elif channel == 'instagram':
            lead, created = Lead.objects.get_or_create(
                organization=org,
                instagram_user_id=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                    'phone': '', 'is_ai_active': bot_active,
                }
            )
        else:  # whatsapp
            lead, created = Lead.objects.get_or_create(
                organization=org,
                phone=sender_id,
                defaults={
                    'status': 'NEW', 'source': 'OTHER', 'channels_used': channel,
                    'conversation_state': 'initial', 'full_name': contact_name or '',
                    'is_ai_active': bot_active,
                }
            )

        # Se o bot foi desativado globalmente depois que o lead já existia,
        # respeita o is_ai_active individual do lead (não força para False).
        # Mas se o bot foi desativado e o lead acabou de ser criado, já está False acima.

        if not created and lead.is_archived:
            fields_to_update = ['is_archived']
            lead.is_archived = False
            if contact_name and not lead.full_name:
                lead.full_name = contact_name
                fields_to_update.append('full_name')
            lead.save(update_fields=fields_to_update)
        elif not created and contact_name and not lead.full_name:
            lead.full_name = contact_name
            lead.save(update_fields=['full_name'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel=channel,
            defaults={'organization': org, 'state': 'active', 'last_message_at': timezone.now()},
        )
        now = timezone.now()
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=now)
        Lead.objects.filter(pk=lead.pk).update(updated_at=now)

        Message.objects.create(
            conversation=conv, organization=org, direction='IN', text=text,
        )

        # Classificação psicológica em background — nunca bloqueia o webhook
        _run_ai_classification(lead, org)

        _notify_users_via_whatsapp(org=org, lead=lead, text=text, channel_provider=channel_provider)

        # ── Mensagem inicial + mídia + sequência (somente no primeiro contato) ──
        if created:
            _send_welcome_sequence(
                org=org, lead=lead, conv=conv,
                channel=channel, channel_provider=channel_provider,
            )

        if not lead.is_ai_active or not bot_active:
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

        # Vectoriza par IN/OUT do bot automaticamente em background
        if reply_texts and text:
            _vectorize_bot_reply(org, lead, text, reply_texts[0])

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

        lead, ig_created = Lead.objects.get_or_create(
            organization=org,
            instagram_user_id=sender_id,
            defaults={
                'status': 'NEW', 'source': 'INSTAGRAM_AD', 'channels_used': 'instagram',
                'conversation_state': 'initial', 'full_name': sender_name or '',
                'phone': '',
            }
        )

        if not ig_created and lead.is_archived:
            lead.is_archived = False
            lead.save(update_fields=['is_archived'])

        conv, _ = Conversation.objects.get_or_create(
            lead=lead, channel='instagram',
            defaults={'organization': org, 'state': 'active', 'last_message_at': timezone.now()},
        )
        now = timezone.now()
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=now)
        Lead.objects.filter(pk=lead.pk).update(updated_at=now)

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


def _vectorize_bot_reply(org, lead, message_in: str, message_out: str):
    """Vectoriza par IN/OUT gerado pelo bot em background thread."""
    import threading

    def _run():
        try:
            cfg = org.agent_config
            if not cfg.is_ready():
                return
            skip_words = ['[vídeo]', '[imagem]', '[documento]', '[mídia]']
            if any(w in message_out for w in skip_words):
                return
            from apps.rag.services.training_service import store_conversation_pair
            store_conversation_pair(cfg, message_in, message_out, lead)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f'_vectorize_bot_reply error: {e}')

    threading.Thread(target=_run, daemon=True).start()


def _run_ai_classification(lead, org):
    """Lança classificação psicológica do lead em background thread."""
    import threading

    def _run():
        try:
            cfg = org.agent_config
            if not getattr(cfg, 'openai_api_key', None):
                return
            from apps.qualifier.ai_classifier import AILeadClassifier
            classifier = AILeadClassifier(lead, cfg)
            result = classifier.classify()
            if result:
                classifier._map_to_db(result)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f'_run_ai_classification error: {e}')

    threading.Thread(target=_run, daemon=True).start()


def _send_welcome_sequence(org, lead, conv, channel, channel_provider):
    """Envia a mensagem inicial, mídias anexadas e mensagem de sequência configuradas na org."""
    import time
    import logging
    logger = logging.getLogger('apps')

    try:
        cfg = org.agent_config
    except AgentConfig.DoesNotExist:
        return

    # Resolve channel_provider se ainda não foi passado
    if channel_provider is None:
        channel_provider = ChannelProvider.objects.filter(
            organization=org, provider=channel, is_active=True,
        ).first()

    def _save_and_send(text_or_media):
        """Salva no banco e envia pelo canal."""
        is_media = isinstance(text_or_media, dict)
        db_text = (
            text_or_media.get('caption') or f"[{text_or_media.get('type', 'mídia')}]"
            if is_media else text_or_media
        )
        Message.objects.create(
            conversation=conv, organization=org, direction='OUT', text=db_text,
        )
        if not channel_provider or not channel_provider.access_token:
            return
        if is_media:
            if channel == 'whatsapp' and channel_provider.phone_number_id:
                _send_whatsapp_media(
                    phone_number_id=channel_provider.phone_number_id,
                    access_token=channel_provider.access_token,
                    to=lead.phone,
                    media_type=text_or_media.get('type', 'image'),
                    url=text_or_media['url'],
                    caption=text_or_media.get('caption', ''),
                )
        else:
            if channel in ('messenger', 'facebook'):
                _send_facebook_message(
                    page_id=channel_provider.page_id,
                    access_token=channel_provider.access_token,
                    recipient_id=lead.facebook_psid or '',
                    text=text_or_media,
                )
            elif channel == 'instagram':
                _send_instagram_message(
                    instagram_account_id=channel_provider.instagram_account_id,
                    access_token=channel_provider.access_token,
                    recipient_id=lead.instagram_user_id or '',
                    text=text_or_media,
                )
            elif channel_provider.phone_number_id:
                _send_whatsapp_message(
                    phone_number_id=channel_provider.phone_number_id,
                    access_token=channel_provider.access_token,
                    to=lead.phone,
                    text=text_or_media,
                )

    try:
        # 1. Mensagem inicial (texto)
        if cfg.initial_message and cfg.initial_message.strip():
            _save_and_send(cfg.initial_message.strip())
            time.sleep(1)

        # 2. Mídias anexadas (fotos/vídeos)
        media_items = cfg.initial_media.all()
        for item in media_items:
            request_obj = None
            # Monta URL absoluta para o arquivo
            from django.conf import settings as django_settings
            base_url = getattr(django_settings, 'MEDIA_BASE_URL', '').rstrip('/')
            if not base_url:
                # fallback: tenta construir pela variável NGROK se existir
                base_url = getattr(django_settings, '_NGROK', '').rstrip('/')
            file_url = f'{base_url}{item.file.url}' if base_url else item.file.url
            _save_and_send({'type': item.media_type, 'url': file_url, 'caption': ''})
            delay = 7 if item.media_type == 'video' else 3
            time.sleep(delay)

        # 3. Mensagem de sequência (texto)
        if cfg.sequence_message and cfg.sequence_message.strip():
            time.sleep(1)
            _save_and_send(cfg.sequence_message.strip())

    except Exception as e:
        logger.warning(f'_send_welcome_sequence error: {e}')


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


def _is_whatsapp_window_open(conversation):
    """Retorna True se a janela de sessão de 24h do WhatsApp ainda está aberta."""
    from django.utils import timezone
    if not conversation or not conversation.last_message_at:
        return False
    delta = timezone.now() - conversation.last_message_at
    return delta.total_seconds() < 86400  # 24 horas


def _resolve_whatsapp_media_ref(media_url: str, channel_provider, request=None) -> dict:
    """
    Given a media URL (relative /media/... or absolute http...), returns either
    {'id': '<whatsapp_media_id>'} (preferred — no public URL needed) or
    {'link': '<public_url>'} (fallback when upload fails or file not on disk).
    """
    import requests as http_requests
    import mimetypes as _mimetypes
    from pathlib import Path
    from django.conf import settings as django_settings

    # If already an absolute external URL, return as link directly.
    if media_url.startswith('http'):
        return {'link': media_url}

    # Resolve file path on disk from relative /media/... path.
    if media_url.startswith('/media/'):
        rel = media_url[len('/media/'):]
    elif '/media/' in media_url:
        rel = media_url.split('/media/', 1)[1]
    else:
        rel = None

    file_path = Path(django_settings.MEDIA_ROOT) / rel if rel else None

    if file_path and file_path.exists():
        try:
            mime = _mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
            upload_url = f'https://graph.facebook.com/v22.0/{channel_provider.phone_number_id}/media'
            with open(file_path, 'rb') as fh:
                resp = http_requests.post(
                    upload_url,
                    headers={'Authorization': f'Bearer {channel_provider.access_token}'},
                    data={'messaging_product': 'whatsapp'},
                    files={'file': (file_path.name, fh, mime)},
                    timeout=60,
                )
            if resp.status_code == 200:
                media_id = resp.json().get('id')
                if media_id:
                    return {'id': media_id}
            logger.warning(f'WA media upload failed ({resp.status_code}): {resp.text}')
        except Exception as e:
            logger.warning(f'WA media upload error: {e}')

    # Fallback: reconstruct public URL (requires ngrok/public host to be reachable).
    _base = (django_settings.MEDIA_BASE_URL or '').rstrip('/')
    if _base:
        public_url = f'{_base}{media_url}'
    elif request:
        public_url = request.build_absolute_uri(media_url)
    else:
        public_url = media_url
    logger.warning(f'WA media: using link fallback {public_url}')
    return {'link': public_url}


def _send_whatsapp_template(phone_number_id, access_token, to, template_name, language_code, components=None):
    """Envia template HSM aprovado via WhatsApp Cloud API. Retorna wamid ou None."""
    import requests as http_requests

    url = f'https://graph.facebook.com/v22.0/{phone_number_id}/messages'
    template_payload = {
        'name': template_name,
        'language': {'code': language_code},
    }
    if components:
        template_payload['components'] = components
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'template',
        'template': template_payload,
    }
    try:
        resp = http_requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f'WhatsApp template send error: {resp.status_code} {resp.text}')
            return None
        data = resp.json()
        wamid = data.get('messages', [{}])[0].get('id')
        logger.info(f'WhatsApp template "{template_name}" sent to {to} | wamid={wamid}')
        return wamid
    except Exception as e:
        logger.error(f'WhatsApp template send exception: {e}')
        return None


def _notify_users_via_whatsapp(org, lead, text, channel_provider=None):
    """Envia notificação via template WhatsApp para todos os usuários da org com phone cadastrado."""
    try:
        from apps.core.models import UserProfile
        if channel_provider is None:
            channel_provider = ChannelProvider.objects.filter(
                organization=org, provider='whatsapp', is_active=True,
            ).first()
        if not channel_provider or not channel_provider.access_token or not channel_provider.phone_number_id:
            return

        recipients = UserProfile.objects.filter(
            organization=org,
        ).exclude(phone='').values_list('phone', flat=True)

        if not recipients:
            return

        lead_name = lead.full_name or lead.phone or 'Desconhecido'
        msg_preview = (text or '').strip()[:100]

        components = [
            {
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': lead_name},
                    {'type': 'text', 'text': msg_preview or '(mídia)'},
                ],
            }
        ]

        for phone in recipients:
            _send_whatsapp_template(
                phone_number_id=channel_provider.phone_number_id,
                access_token=channel_provider.access_token,
                to=phone,
                template_name='notificacao_pessoal',
                language_code='pt_BR',
                components=components,
            )
    except Exception as e:
        logger.warning(f'_notify_users_via_whatsapp error: {e}')


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


# ─── Message Templates ─────────────────────────────────────────────────────────

class MessageTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageTemplateSerializer

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return MessageTemplate.objects.none()
        return MessageTemplate.objects.filter(organization=org).select_related('channel')

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        is_draft = str(self.request.data.get('draft', '')).lower() in ('true', '1', 'yes')
        if is_draft:
            serializer.save(organization=org, status='DRAFT')
        else:
            instance = serializer.save(organization=org)
            self._submit_to_meta(instance)

    def perform_update(self, serializer):
        is_draft = str(self.request.data.get('draft', '')).lower() in ('true', '1', 'yes')
        if is_draft:
            serializer.save(status='DRAFT')
        else:
            instance = serializer.save()
            if instance.status in ('PENDING', 'REJECTED', 'DRAFT'):
                self._submit_to_meta(instance)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit_for_approval(self, request, pk=None):
        """Envia um rascunho ou template rejeitado para aprovação na Meta."""
        template = self.get_object()
        if template.status not in ('DRAFT', 'REJECTED'):
            return Response(
                {'detail': 'Apenas rascunhos e templates rejeitados podem ser submetidos para aprovação.'},
                status=400,
            )
        try:
            self._submit_to_meta(template)
        except RuntimeError as e:
            template.refresh_from_db()
            return Response(
                {'detail': str(e), 'template': MessageTemplateSerializer(template).data},
                status=502,
            )
        template.refresh_from_db()
        return Response(MessageTemplateSerializer(template).data)

    def _upload_media_to_meta(self, channel, media_url, header_type):
        """
        Faz upload de uma mídia para o WhatsApp API da Meta e retorna o media_id
        para uso como header_handle na criação do template.
        Retorna None em caso de falha.
        """
        import requests as http_requests
        import os

        mime_map = {
            'IMAGE': 'image/jpeg',
            'VIDEO': 'video/mp4',
            'DOCUMENT': 'application/pdf',
        }
        file_type = mime_map.get(header_type.upper(), 'application/octet-stream')

        try:
            logger.info(f'Baixando mídia de {media_url} para upload na Meta...')
            media_resp = http_requests.get(media_url, timeout=30)
            if media_resp.status_code != 200:
                logger.error(f'Falha ao baixar mídia: HTTP {media_resp.status_code}')
                return None
            file_data = media_resp.content
            file_name = os.path.basename(media_url.split('?')[0]) or 'media'

            # Upload via endpoint de mídia do WhatsApp
            upload_resp = http_requests.post(
                f'https://graph.facebook.com/v22.0/{channel.phone_number_id}/media',
                headers={'Authorization': f'Bearer {channel.access_token}'},
                data={'messaging_product': 'whatsapp', 'type': file_type},
                files={'file': (file_name, file_data, file_type)},
                timeout=60,
            )
            upload_data = upload_resp.json()
            media_id = upload_data.get('id')
            if not media_id:
                logger.error(f'Upload da mídia não retornou id: {upload_data}')
                return None

            logger.info(f'Mídia enviada para Meta: media_id={media_id}')
            return media_id

        except Exception as e:
            logger.error(f'Exceção ao fazer upload de mídia para a Meta: {e}')
            return None

    def _submit_to_meta(self, template):
        """Envia o template para aprovação na Meta."""
        channel = template.channel
        if not channel or not channel.business_account_id or not channel.access_token:
            logger.warning(f'MessageTemplate {template.id}: canal sem credenciais Meta, pulando submissão.')
            return

        import requests as http_requests
        url = f'https://graph.facebook.com/v22.0/{channel.business_account_id}/message_templates'
        components = []
        header_type = (template.header_type or 'NONE').upper()
        if header_type == 'TEXT' and template.header_text:
            components.append({'type': 'HEADER', 'format': 'TEXT', 'text': template.header_text})
        elif header_type in ('IMAGE', 'VIDEO', 'DOCUMENT'):
            # Para templates com mídia, a Meta requer um media_handle (obtido via
            # Resumable Upload API) no campo example.header_handle.
            # Se o template tiver um meta_media_handle salvo, usa ele.
            # Caso contrário, tenta subir o arquivo e obter o handle.
            header_component = {'type': 'HEADER', 'format': header_type}
            media_handle = getattr(template, 'meta_media_handle', None)
            if not media_handle and template.header_media_url:
                media_handle = self._upload_media_to_meta(
                    channel, template.header_media_url, header_type
                )
                if media_handle:
                    try:
                        template.meta_media_handle = media_handle
                        template.save(update_fields=['meta_media_handle'])
                    except Exception:
                        pass
            if media_handle:
                header_component['example'] = {'header_handle': [media_handle]}
            components.append(header_component)
        components.append({'type': 'BODY', 'text': template.body_text})
        if template.footer_text:
            components.append({'type': 'FOOTER', 'text': template.footer_text})

        payload = {
            'name': template.name,
            'language': template.language,
            'category': template.category,
            'components': components,
        }
        try:
            resp = http_requests.post(
                url,
                json=payload,
                headers={'Authorization': f'Bearer {channel.access_token}', 'Content-Type': 'application/json'},
                timeout=45,
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                template.meta_template_id = data.get('id', '')
                template.status = 'PENDING'
                template.rejection_reason = ''
                template.save(update_fields=['meta_template_id', 'status', 'rejection_reason'])
                logger.info(f'Template "{template.name}" submetido à Meta: id={template.meta_template_id}')
            else:
                raw_error = data.get('error', {})
                error_msg = raw_error.get('error_user_msg') or raw_error.get('message', str(data))
                # Se é erro 500 da Meta com cabeçalho de mídia, orientar o usuário
                if resp.status_code == 500 and (template.header_type or '').upper() in ('IMAGE', 'VIDEO', 'DOCUMENT'):
                    error_msg = (
                        'A API da Meta não conseguiu processar o cabeçalho de mídia via API. '
                        'Crie este template diretamente em '
                        'business.facebook.com → WhatsApp Manager → Templates de mensagem, '
                        'faça o upload do vídeo/imagem lá e clique em Enviar para aprovação. '
                        'O webhook atualizará o status aqui automaticamente quando for aprovado.'
                    )
                template.status = 'DRAFT'
                template.rejection_reason = error_msg
                template.save(update_fields=['status', 'rejection_reason'])
                logger.error(f'Erro ao submeter template "{template.name}" à Meta: {error_msg}')
                raise RuntimeError(error_msg)
        except http_requests.exceptions.Timeout:
            msg = 'A API da Meta demorou mais de 45s para responder. Tente novamente em alguns minutos.'
            template.rejection_reason = msg
            template.save(update_fields=['rejection_reason'])
            logger.error(f'Timeout ao submeter template "{template.name}" à Meta.')
            raise RuntimeError(msg)
        except RuntimeError:
            raise
        except Exception as e:
            msg = str(e)
            template.rejection_reason = msg
            template.save(update_fields=['rejection_reason'])
            logger.error(f'Exceção ao submeter template à Meta: {e}')
            raise RuntimeError(msg)

    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        """Sincroniza o status de um template específico com a Meta."""
        template = self.get_object()
        channel = template.channel
        if not channel or not channel.business_account_id or not channel.access_token:
            return Response({'detail': 'Canal sem credenciais Meta.'}, status=400)
        if not template.meta_template_id:
            return Response({'detail': 'Template ainda não foi submetido à Meta.'}, status=400)

        import requests as http_requests
        url = f'https://graph.facebook.com/v22.0/{template.meta_template_id}'
        try:
            resp = http_requests.get(
                url,
                params={'fields': 'id,name,status,quality_score,rejected_reason'},
                headers={'Authorization': f'Bearer {channel.access_token}'},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code == 200:
                meta_status = data.get('status', '').upper()
                STATUS_MAP = {
                    'APPROVED': 'APPROVED', 'REJECTED': 'REJECTED',
                    'PENDING': 'PENDING', 'PAUSED': 'PAUSED', 'DISABLED': 'DISABLED',
                }
                template.status = STATUS_MAP.get(meta_status, 'PENDING')
                template.rejection_reason = data.get('rejected_reason', '')
                template.save(update_fields=['status', 'rejection_reason'])
                return Response(MessageTemplateSerializer(template).data)
            else:
                return Response({'detail': data.get('error', {}).get('message', 'Erro Meta')}, status=400)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=True, methods=['post'], url_path='link')
    def link_meta_id(self, request, pk=None):
        """
        Vincula um template criado manualmente no Meta Business Manager.
        Recebe { "meta_template_id": "123456789" }, verifica na API da Meta
        e atualiza status e meta_template_id localmente.
        """
        template = self.get_object()
        meta_id = str(request.data.get('meta_template_id', '')).strip()
        if not meta_id:
            return Response({'detail': 'Informe o meta_template_id.'}, status=400)

        channel = template.channel
        if not channel or not channel.business_account_id or not channel.access_token:
            return Response({'detail': 'Canal sem credenciais Meta.'}, status=400)

        import requests as http_requests
        try:
            resp = http_requests.get(
                f'https://graph.facebook.com/v22.0/{meta_id}',
                params={'fields': 'id,name,status,rejected_reason,category,language'},
                headers={'Authorization': f'Bearer {channel.access_token}'},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code != 200:
                err = data.get('error', {}).get('message', str(data))
                return Response({'detail': f'ID não encontrado na Meta: {err}'}, status=400)

            STATUS_MAP = {
                'APPROVED': 'APPROVED', 'REJECTED': 'REJECTED',
                'PENDING': 'PENDING', 'PAUSED': 'PAUSED', 'DISABLED': 'DISABLED',
            }
            meta_status = data.get('status', '').upper()
            template.meta_template_id = meta_id
            template.status = STATUS_MAP.get(meta_status, 'PENDING')
            template.rejection_reason = data.get('rejected_reason', '') or ''
            if template.rejection_reason == 'NONE':
                template.rejection_reason = ''
            template.save(update_fields=['meta_template_id', 'status', 'rejection_reason'])
            logger.info(f'Template "{template.name}" vinculado ao meta_id={meta_id}, status={template.status}')
            return Response(MessageTemplateSerializer(template).data)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='sync-all')
    def sync_all(self, request):
        """
        Sincroniza todos os templates da organização com a Meta.
        Templates existentes têm status/rejection_reason atualizados.
        Templates que existem na Meta mas não no banco são importados automaticamente.
        """
        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'Sem organização.'}, status=400)

        import requests as http_requests
        updated = []
        imported = []
        errors = []
        STATUS_MAP = {
            'APPROVED': 'APPROVED', 'REJECTED': 'REJECTED',
            'PENDING': 'PENDING', 'PAUSED': 'PAUSED', 'DISABLED': 'DISABLED',
        }
        HEADER_FORMAT_MAP = {
            'IMAGE': 'IMAGE', 'VIDEO': 'VIDEO', 'DOCUMENT': 'DOCUMENT', 'TEXT': 'TEXT',
        }

        def _parse_components(components):
            """Extrai header_type, header_text, body_text e footer_text de components[]."""
            header_type = 'NONE'
            header_text = ''
            body_text = ''
            footer_text = ''
            for comp in (components or []):
                ctype = comp.get('type', '').upper()
                if ctype == 'HEADER':
                    fmt = comp.get('format', '').upper()
                    header_type = HEADER_FORMAT_MAP.get(fmt, 'NONE')
                    if header_type == 'TEXT':
                        header_text = comp.get('text', '')
                elif ctype == 'BODY':
                    body_text = comp.get('text', '')
                elif ctype == 'FOOTER':
                    footer_text = comp.get('text', '')
            return header_type, header_text, body_text, footer_text

        channels = ChannelProvider.objects.filter(organization=org, is_active=True)
        for channel in channels:
            if not channel.business_account_id or not channel.access_token:
                continue
            url = f'https://graph.facebook.com/v22.0/{channel.business_account_id}/message_templates'
            try:
                resp = http_requests.get(
                    url,
                    params={
                        'fields': 'id,name,status,rejected_reason,category,language,components',
                        'limit': 100,
                    },
                    headers={'Authorization': f'Bearer {channel.access_token}'},
                    timeout=15,
                )
                if resp.status_code != 200:
                    errors.append(f'Canal {channel.name}: {resp.text}')
                    continue
                data = resp.json().get('data', [])
                for item in data:
                    tmpl = MessageTemplate.objects.filter(
                        organization=org, meta_template_id=item['id']
                    ).first()
                    if not tmpl:
                        tmpl = MessageTemplate.objects.filter(
                            organization=org,
                            name=item['name'],
                            language=item.get('language', 'pt_BR'),
                        ).first()

                    meta_status = STATUS_MAP.get(item.get('status', '').upper(), 'PENDING')
                    rejection = item.get('rejected_reason', '') or ''
                    if rejection == 'NONE':
                        rejection = ''

                    if tmpl:
                        tmpl.meta_template_id = item['id']
                        tmpl.status = meta_status
                        tmpl.rejection_reason = rejection
                        tmpl.save(update_fields=['meta_template_id', 'status', 'rejection_reason'])
                        updated.append(tmpl.name)
                    else:
                        # Importa template que só existe na Meta
                        header_type, header_text, body_text, footer_text = _parse_components(
                            item.get('components', [])
                        )
                        category = item.get('category', 'UTILITY').upper()
                        if category not in ('MARKETING', 'UTILITY', 'AUTHENTICATION'):
                            category = 'UTILITY'
                        language = item.get('language', 'pt_BR')
                        new_tmpl = MessageTemplate.objects.create(
                            organization=org,
                            channel=channel,
                            name=item['name'],
                            language=language,
                            category=category,
                            header_type=header_type,
                            header_text=header_text,
                            body_text=body_text,
                            footer_text=footer_text,
                            meta_template_id=item['id'],
                            status=meta_status,
                            rejection_reason=rejection,
                        )
                        logger.info(
                            f'Template importado da Meta: "{new_tmpl.name}" '
                            f'[{language}] status={meta_status}'
                        )
                        imported.append(new_tmpl.name)
            except Exception as e:
                errors.append(f'Canal {channel.name}: {e}')

        return Response({'updated': updated, 'imported': imported, 'errors': errors})


# ─── Gallery ───────────────────────────────────────────────────────────────────

class GalleryMediaViewSet(viewsets.ModelViewSet):
    """CRUD de mídia da galeria (imagens e vídeos) por organização."""
    permission_classes = [IsAuthenticated]
    serializer_class = GalleryMediaSerializer
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            return GalleryMedia.objects.none()
        qs = GalleryMedia.objects.filter(organization=org)
        media_type = self.request.query_params.get('media_type')
        if media_type in ('IMAGE', 'VIDEO'):
            qs = qs.filter(media_type=media_type)
        return qs

    def create(self, request, *args, **kwargs):
        import mimetypes, os, uuid as uuid_mod
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        from django.conf import settings as django_settings

        org = _get_org(request.user)
        if not org:
            return Response({'detail': 'Sem organização.'}, status=400)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'Arquivo obrigatório.'}, status=400)

        mime = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or ''
        if mime.startswith('image/'):
            media_type = 'IMAGE'
        elif mime.startswith('video/'):
            media_type = 'VIDEO'
        elif mime == 'application/pdf':
            media_type = 'DOCUMENT'
        else:
            return Response({'detail': 'Tipo não suportado. Envie imagens, vídeos ou PDFs.'}, status=400)

        max_bytes = 100 * 1024 * 1024  # 100 MB (PDFs podem ser maiores)
        if uploaded.size > max_bytes:
            return Response({'detail': 'Arquivo muito grande. Máximo: 100 MB.'}, status=400)

        ext = os.path.splitext(uploaded.name)[1].lower() or ''
        filename = f'gallery/{org.id}/{uuid_mod.uuid4().hex}{ext}'
        saved_path = default_storage.save(filename, ContentFile(uploaded.read()))

        # Armazena como path relativo (/media/...) para funcionar tanto em dev
        # (proxy Vite) quanto em produção sem depender do ngrok estar ativo.
        file_url = f'/media/{saved_path}'

        item = GalleryMedia.objects.create(
            organization=org,
            name=request.data.get('name', '') or uploaded.name,
            description=request.data.get('description', ''),
            file_url=file_url,
            mime_type=mime,
            media_type=media_type,
            size_bytes=uploaded.size,
        )
        return Response(GalleryMediaSerializer(item).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        allowed = {k: v for k, v in request.data.items() if k in ('name', 'description')}
        serializer = GalleryMediaSerializer(instance, data=allowed, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def perform_destroy(self, instance):
        import os
        from django.core.files.storage import default_storage
        try:
            path = instance.file_url.split('/media/')[-1]
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception:
            pass
        instance.delete()


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


# ─── Server Config ────────────────────────────────────────────────────────────

class ServerConfigView(APIView):
    """Expõe configurações públicas do servidor para o frontend (somente leitura)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings as django_settings
        return Response({
            'media_base_url': django_settings.MEDIA_BASE_URL or '',
        })


# ─── Generic Media Upload ─────────────────────────────────────────────────────

class UploadMediaView(APIView):
    """Upload de imagem, vídeo ou documento para uso em templates de mensagem.

    Salva o arquivo em media/template_media/ e retorna a URL pública absoluta.
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_MIME_PREFIXES = ('image/', 'video/')
    ALLOWED_MIMES = ('application/pdf',)
    MAX_SIZE_BYTES = 16 * 1024 * 1024  # 16 MB

    def post(self, request):
        import mimetypes, os, uuid
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'Arquivo obrigatório.'}, status=400)

        mime = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or ''
        is_allowed = (
            any(mime.startswith(p) for p in self.ALLOWED_MIME_PREFIXES)
            or mime in self.ALLOWED_MIMES
        )
        if not is_allowed:
            return Response(
                {'detail': f'Tipo de arquivo não suportado ({mime}). Aceitos: imagens, vídeos e PDFs.'},
                status=400,
            )

        if uploaded.size > self.MAX_SIZE_BYTES:
            mb = self.MAX_SIZE_BYTES // (1024 * 1024)
            return Response({'detail': f'Arquivo muito grande. Máximo: {mb} MB.'}, status=400)

        ext = os.path.splitext(uploaded.name)[1].lower() or ''
        filename = f'template_media/{uuid.uuid4().hex}{ext}'
        saved_path = default_storage.save(filename, ContentFile(uploaded.read()))

        from django.conf import settings as django_settings
        base = (django_settings.MEDIA_BASE_URL or '').rstrip('/')
        if base:
            url = f'{base}/media/{saved_path}'
        else:
            url = request.build_absolute_uri(f'/media/{saved_path}')

        return Response({'url': url, 'name': uploaded.name, 'mime': mime}, status=201)


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


# ─── Contracts ────────────────────────────────────────────────────────────────

class ContractViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContractSerializer

    def get_queryset(self):
        org = _get_org(self.request.user)
        if not org:
            from apps.contracts.models import SaleContract
            return SaleContract.objects.none()
        from apps.contracts.models import SaleContract
        qs = SaleContract.objects.filter(organization=org).select_related('lead')
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        contract = self.get_object()
        if contract.status not in ('draft',):
            return Response({'detail': 'Contrato já foi enviado.'}, status=400)
        from django.conf import settings as dj_settings
        from django.utils import timezone as tz
        contract.status = 'sent'
        contract.save(update_fields=['status', 'updated_at'])

        base = (dj_settings.MEDIA_BASE_URL or '').rstrip('/')
        link = f"{base}/contrato/{contract.token}"

        if contract.lead and contract.lead.phone:
            msg = (
                f"Olá! Seu contrato de compra do filhote Border Collie está pronto para preenchimento.\n\n"
                f"Acesse o link abaixo, preencha seus dados e aguarde a aprovação:\n{link}"
            )
            try:
                _send_whatsapp_to_lead(contract.lead, msg)
            except Exception as e:
                logger.warning("Falha ao enviar WhatsApp para contrato #%s: %s", contract.id, e)

        serializer = self.get_serializer(contract)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        contract = self.get_object()
        if contract.status != 'buyer_filled':
            return Response({'detail': 'Aguardando o comprador preencher o contrato.'}, status=400)
        from django.utils import timezone as tz
        from django.conf import settings as dj_settings
        contract.status = 'approved'
        contract.approved_at = tz.now()
        contract.save(update_fields=['status', 'approved_at', 'updated_at'])

        base = (dj_settings.MEDIA_BASE_URL or '').rstrip('/')
        link = f"{base}/contrato/{contract.token}"

        if contract.lead and contract.lead.phone:
            msg = (
                f"Seu contrato foi aprovado! Agora você pode assinar digitalmente.\n\n"
                f"Acesse o link para assinar:\n{link}"
            )
            try:
                _send_whatsapp_to_lead(contract.lead, msg)
            except Exception as e:
                logger.warning("Falha ao enviar WhatsApp (approve) para contrato #%s: %s", contract.id, e)

        serializer = self.get_serializer(contract)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def generate_pdf(self, request, pk=None):
        from apps.contracts.pdf_utils import generate_contract_pdf
        from django.http import HttpResponse
        contract = self.get_object()
        try:
            pdf_bytes = generate_contract_pdf(contract)
        except RuntimeError as e:
            return Response({'detail': str(e)}, status=500)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="contrato_{contract.id}.pdf"'
        return response

    @action(detail=True, methods=['get'])
    def preview_html(self, request, pk=None):
        from apps.contracts.pdf_utils import render_contract_html
        from django.http import HttpResponse
        contract = self.get_object()
        html = render_contract_html(contract)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    @action(detail=True, methods=['post'])
    def send_whatsapp(self, request, pk=None):
        contract = self.get_object()
        if not contract.lead or not contract.lead.phone:
            return Response({'detail': 'Lead sem telefone cadastrado.'}, status=400)
        from django.conf import settings as dj_settings
        base = (dj_settings.MEDIA_BASE_URL or '').rstrip('/')
        link = f"{base}/contrato/{contract.token}"
        custom_msg = request.data.get('message', '')
        msg = custom_msg or f"Acesse seu contrato: {link}"
        try:
            _send_whatsapp_to_lead(contract.lead, msg)
        except Exception as e:
            return Response({'detail': f'Erro ao enviar WhatsApp: {e}'}, status=500)
        return Response({'detail': 'Mensagem enviada com sucesso.'})


def _send_whatsapp_to_lead(lead, message):
    """Envia mensagem WhatsApp para o lead usando o canal ativo da organização."""
    from apps.channels.models import ChannelProvider
    channel = ChannelProvider.objects.filter(
        organization=lead.organization, provider='whatsapp', is_active=True
    ).first()
    if not channel:
        raise ValueError('Nenhum canal WhatsApp ativo configurado.')
    _send_whatsapp_message(
        channel=channel,
        to=lead.phone,
        message=message,
    )


# ─── Public Contract Views ────────────────────────────────────────────────────

class PublicContractView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        from apps.contracts.models import SaleContract
        try:
            contract = SaleContract.objects.get(token=token)
        except SaleContract.DoesNotExist:
            return Response({'detail': 'Contrato não encontrado.'}, status=404)
        if contract.status == 'draft':
            return Response({'detail': 'Este contrato ainda não foi liberado.'}, status=403)
        serializer = ContractPublicSerializer(contract)
        return Response(serializer.data)


class PublicContractFillView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        from apps.contracts.models import SaleContract
        from django.utils import timezone as tz
        try:
            contract = SaleContract.objects.get(token=token)
        except SaleContract.DoesNotExist:
            return Response({'detail': 'Contrato não encontrado.'}, status=404)

        if contract.status != 'sent':
            return Response({'detail': 'Este contrato não está disponível para preenchimento.'}, status=400)

        data = request.data
        contract.buyer_name = data.get('buyer_name', '').strip()
        contract.buyer_cpf = data.get('buyer_cpf', '').strip()
        contract.buyer_marital_status = data.get('buyer_marital_status', '').strip()
        contract.buyer_address = data.get('buyer_address', '').strip()
        contract.buyer_cep = data.get('buyer_cep', '').strip()
        contract.buyer_email = data.get('buyer_email', '').strip()
        contract.status = 'buyer_filled'
        contract.buyer_filled_at = tz.now()
        contract.save(update_fields=[
            'buyer_name', 'buyer_cpf', 'buyer_marital_status',
            'buyer_address', 'buyer_cep', 'buyer_email',
            'status', 'buyer_filled_at', 'updated_at',
        ])
        serializer = ContractPublicSerializer(contract)
        return Response(serializer.data)


class PublicContractSignView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        from apps.contracts.models import SaleContract
        from apps.contracts.pdf_utils import generate_contract_pdf
        from django.utils import timezone as tz
        try:
            contract = SaleContract.objects.get(token=token)
        except SaleContract.DoesNotExist:
            return Response({'detail': 'Contrato não encontrado.'}, status=404)

        if contract.status != 'approved':
            return Response({'detail': 'Este contrato ainda não foi aprovado para assinatura.'}, status=400)

        signature_data = request.data.get('signature_data', '')
        signature_type = request.data.get('signature_type', 'canvas')

        if not signature_data:
            return Response({'detail': 'Dados de assinatura não informados.'}, status=400)

        contract.signature_data = signature_data
        contract.signature_type = signature_type
        contract.status = 'signed'
        contract.signed_at = tz.now()
        contract.save(update_fields=[
            'signature_data', 'signature_type', 'status', 'signed_at', 'updated_at'
        ])

        try:
            generate_contract_pdf(contract)
        except Exception as e:
            logger.warning("Falha ao gerar PDF após assinatura do contrato #%s: %s", contract.id, e)

        serializer = ContractPublicSerializer(contract)
        return Response(serializer.data)


# ─── Generic Notes ────────────────────────────────────────────────────────────

class GenericNoteViewSet(viewsets.ModelViewSet):
    serializer_class = GenericNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.notes.models import GenericNote
        org = _get_org(self.request.user)
        if not org:
            from apps.notes.models import GenericNote as GN
            return GN.objects.none()
        return GenericNote.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org, author=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_pin(self, request, pk=None):
        note = self.get_object()
        note.is_pinned = not note.is_pinned
        note.save(update_fields=['is_pinned', 'updated_at'])
        return Response(self.get_serializer(note).data)


# ─── Kennel ───────────────────────────────────────────────────────────────────

class DogViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from apps.kennel.models import Dog
        org = _get_org(self.request.user)
        if not org:
            return Dog.objects.none()
        qs = Dog.objects.filter(organization=org).select_related(
            'father', 'mother', 'origin_litter'
        ).prefetch_related('media', 'health_records')
        status_filter = self.request.query_params.get('status')
        sex_filter = self.request.query_params.get('sex')
        breed_filter = self.request.query_params.get('breed')
        search = self.request.query_params.get('search')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if sex_filter:
            qs = qs.filter(sex=sex_filter)
        if breed_filter:
            qs = qs.filter(breed__icontains=breed_filter)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return DogListSerializer
        return DogDetailSerializer

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)

    @action(detail=True, methods=['post'])
    def add_media(self, request, pk=None):
        from apps.kennel.models import DogMedia
        dog = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Arquivo não enviado.'}, status=400)
        media = DogMedia.objects.create(
            dog=dog,
            file=file,
            caption=request.data.get('caption', ''),
        )
        return Response(DogMediaSerializer(media, context={'request': request}).data, status=201)

    @action(detail=True, methods=['delete'], url_path='media/(?P<media_id>[0-9]+)')
    def remove_media(self, request, pk=None, media_id=None):
        from apps.kennel.models import DogMedia
        dog = self.get_object()
        try:
            media = DogMedia.objects.get(id=media_id, dog=dog)
            media.file.delete(save=False)
            media.delete()
            return Response(status=204)
        except DogMedia.DoesNotExist:
            return Response({'detail': 'Mídia não encontrada.'}, status=404)


class LitterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from apps.kennel.models import Litter
        org = _get_org(self.request.user)
        if not org:
            return Litter.objects.none()
        return Litter.objects.filter(organization=org).select_related(
            'father', 'mother'
        ).prefetch_related('media', 'health_records', 'puppies', 'puppies__media')

    def get_serializer_class(self):
        if self.action == 'list':
            return LitterListSerializer
        return LitterDetailSerializer

    def perform_create(self, serializer):
        org = _get_org(self.request.user)
        serializer.save(organization=org)

    @action(detail=True, methods=['post'])
    def add_media(self, request, pk=None):
        from apps.kennel.models import LitterMedia
        litter = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Arquivo não enviado.'}, status=400)
        media = LitterMedia.objects.create(
            litter=litter,
            file=file,
            caption=request.data.get('caption', ''),
        )
        return Response(LitterMediaSerializer(media, context={'request': request}).data, status=201)

    @action(detail=True, methods=['delete'], url_path='media/(?P<media_id>[0-9]+)')
    def remove_media(self, request, pk=None, media_id=None):
        from apps.kennel.models import LitterMedia
        litter = self.get_object()
        try:
            media = LitterMedia.objects.get(id=media_id, litter=litter)
            media.file.delete(save=False)
            media.delete()
            return Response(status=204)
        except LitterMedia.DoesNotExist:
            return Response({'detail': 'Mídia não encontrada.'}, status=404)


class DogHealthRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DogHealthRecordSerializer
    pagination_class = None

    def get_queryset(self):
        from apps.kennel.models import DogHealthRecord
        org = _get_org(self.request.user)
        if not org:
            return DogHealthRecord.objects.none()
        qs = DogHealthRecord.objects.filter(dog__organization=org).select_related('dog')
        dog_id = self.request.query_params.get('dog')
        if dog_id:
            qs = qs.filter(dog_id=dog_id)
        return qs


class LitterHealthRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LitterHealthRecordSerializer
    pagination_class = None

    def get_queryset(self):
        from apps.kennel.models import LitterHealthRecord
        org = _get_org(self.request.user)
        if not org:
            return LitterHealthRecord.objects.none()
        qs = LitterHealthRecord.objects.filter(litter__organization=org).select_related('litter')
        litter_id = self.request.query_params.get('litter')
        if litter_id:
            qs = qs.filter(litter_id=litter_id)
        return qs


# ─── Public plans endpoint (no authentication required) ──────────────────────

class PublicPlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.core.models import Plan
        from api.serializers import PlanSerializer

        plans = Plan.objects.filter(is_active=True).order_by('price_monthly')
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


# ─── Public kennel endpoints (no authentication required) ────────────────────

class PublicLitterListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.kennel.models import Litter
        from api.serializers import PublicLitterSerializer

        org_id = request.query_params.get('org_id')
        if not org_id:
            return Response({'detail': 'org_id is required.'}, status=400)

        qs = (
            Litter.objects
            .filter(organization_id=org_id)
            .select_related('father', 'mother')
            .prefetch_related('media', 'puppies', 'puppies__media')
            .order_by('-birth_date', '-created_at')
        )
        serializer = PublicLitterSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class PublicLitterDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        from apps.kennel.models import Litter
        from api.serializers import PublicLitterSerializer

        try:
            litter = (
                Litter.objects
                .select_related('father', 'mother')
                .prefetch_related('media', 'puppies', 'puppies__media')
                .get(pk=pk)
            )
        except Litter.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        serializer = PublicLitterSerializer(litter, context={'request': request})
        return Response(serializer.data)
