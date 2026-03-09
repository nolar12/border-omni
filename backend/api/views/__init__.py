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
        lead.is_ai_active = False
        lead.assigned_to = request.user
        lead.status = 'HANDOFF'
        lead.save(update_fields=['is_ai_active', 'assigned_to', 'status'])
        conv, _ = Conversation.objects.get_or_create(lead=lead)
        Message.objects.create(
            conversation=conv,
            direction='OUT',
            text=f"👋 Atendimento assumido por {request.user.first_name}.",
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
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': 'Texto obrigatório.'}, status=400)
        conv, _ = Conversation.objects.get_or_create(lead=lead)
        msg = Message.objects.create(conversation=conv, direction='OUT', text=text)
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
        org_key = request.headers.get('X-ORG-KEY') or data.get('organization_key')
        from_phone = data.get('from_phone', '')
        text = data.get('text', '').strip()
        provider = data.get('provider', 'WHATSAPP')

        try:
            org = Organization.objects.get(api_key=org_key)
        except Organization.DoesNotExist:
            return Response({'detail': 'Organization not found.'}, status=404)

        lead, created = Lead.objects.get_or_create(
            organization=org,
            phone=from_phone,
            defaults={
                'status': 'NEW',
                'source': 'OTHER',
                'channels_used': provider,
                'conversation_state': 'initial',
            }
        )

        if not lead.is_ai_active:
            conv, _ = Conversation.objects.get_or_create(lead=lead)
            Message.objects.create(conversation=conv, direction='IN', text=text)
            return Response({'received': True, 'replies': [], 'lead': _lead_summary(lead)})

        conv, _ = Conversation.objects.get_or_create(lead=lead)
        Message.objects.create(conversation=conv, direction='IN', text=text)

        engine = QualifierEngine(lead)
        replies = engine.process_message(text)

        for reply in replies:
            Message.objects.create(conversation=conv, direction='OUT', text=reply)

        return Response({'received': True, 'replies': replies, 'lead': _lead_summary(lead)})


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
