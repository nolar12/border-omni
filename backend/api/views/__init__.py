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
    def add_note(self, request, pk=None):
        lead = self.get_object()
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)
        note = Note.objects.create(lead=lead, author=request.user, text=text)
        return Response(NoteSerializer(note).data, status=201)

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


# ─── Webhook ──────────────────────────────────────────────────────────────────

class WhatsAppWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        verify_token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')
        if ChannelProvider.objects.filter(webhook_verify_token=verify_token).exists():
            return Response(int(challenge))
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

            # Só processa mensagens de texto por enquanto
            if msg_type != 'text':
                return Response({'received': True, 'note': f'type {msg_type} ignored'}, status=200)

            from_phone = msg['from']           # ex: "5511999999999"
            text = msg['text']['body'].strip()
            phone_number_id = value['metadata']['phone_number_id']

            # Encontra o canal e a organização pelo phone_number_id
            channel = ChannelProvider.objects.filter(phone_number_id=phone_number_id).first()
            if not channel or not channel.organization:
                return Response({'detail': 'Channel not found.'}, status=404)

            org = channel.organization

        except (KeyError, IndexError) as e:
            import logging
            logging.getLogger('apps').error(f'Webhook Meta payload error: {e} | data: {data}')
            return Response({'received': True}, status=200)

        return self._process_message(org=org, from_phone=from_phone, text=text, provider='WHATSAPP')

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

    def _process_message(self, org, from_phone, text, provider='WHATSAPP'):
        """Lógica comum: cria/atualiza lead, roda QualifierEngine, salva e envia mensagens."""
        from django.utils import timezone

        channel = provider.lower() if provider else 'whatsapp'

        lead, _ = Lead.objects.get_or_create(
            organization=org,
            phone=from_phone,
            defaults={
                'status': 'NEW',
                'source': 'OTHER',
                'channels_used': channel,
                'conversation_state': 'initial',
            }
        )

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

        for reply in replies:
            Message.objects.create(
                conversation=conv,
                organization=org,
                direction='OUT',
                text=reply,
            )
            # Envia de volta via WhatsApp API se tiver canal configurado
            if channel_provider and channel_provider.access_token and channel_provider.phone_number_id:
                _send_whatsapp_message(
                    phone_number_id=channel_provider.phone_number_id,
                    access_token=channel_provider.access_token,
                    to=from_phone,
                    text=reply,
                )

        return Response({'received': True, 'replies': replies, 'lead': _lead_summary(lead)})


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
