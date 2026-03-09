from django.contrib.auth.models import User
from rest_framework import serializers
from apps.core.models import Organization, UserProfile, Plan, Subscription
from apps.leads.models import Lead, LeadTag, Note
from apps.conversations.models import Message
from apps.quick_replies.models import QuickReply
from apps.channels.models import ChannelProvider


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'organization_name', 'plan_name']

    def get_organization_name(self, obj):
        try:
            return obj.profile.organization.name
        except Exception:
            return ''

    def get_plan_name(self, obj):
        try:
            return obj.profile.organization.subscription.plan.name
        except Exception:
            return 'free'


# ─── Notes ───────────────────────────────────────────────────────────────────

class NoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = ['id', 'text', 'author_name', 'created_at']

    def get_author_name(self, obj):
        if obj.author:
            return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.email
        return 'Sistema'


# ─── Leads ───────────────────────────────────────────────────────────────────

class AssignedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']


class LeadListSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    assigned_to = AssignedUserSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'phone', 'full_name', 'city', 'state', 'tier', 'score',
            'status', 'source', 'is_ai_active', 'assigned_to', 'tags',
            'created_at', 'updated_at',
        ]

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))


class LeadDetailSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    notes = NoteSerializer(many=True, read_only=True)
    assigned_to = AssignedUserSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'phone', 'full_name', 'instagram_handle', 'city', 'state',
            'housing_type', 'daily_time_minutes', 'experience_level', 'budget_ok',
            'timeline', 'purpose', 'has_kids', 'has_other_pets', 'score', 'tier',
            'status', 'source', 'channels_used', 'is_ai_active', 'assigned_to',
            'conversation_state', 'tags', 'notes', 'created_at', 'updated_at',
        ]

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))


# ─── Messages ────────────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'direction', 'text', 'provider_message_id', 'created_at']


# ─── Quick Replies ────────────────────────────────────────────────────────────

class QuickReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickReply
        fields = ['id', 'category', 'text', 'shortcut', 'is_active', 'created_at']


# ─── Channels ────────────────────────────────────────────────────────────────

class ChannelProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelProvider
        fields = [
            'id', 'provider', 'app_id', 'phone_number_id', 'business_account_id',
            'instagram_account_id', 'page_id', 'webhook_verify_token', 'webhook_url',
            'is_active', 'is_simulated', 'verification_status', 'last_verified_at',
            'created_at', 'updated_at',
        ]
        # access_token is write-only for security
        extra_kwargs = {'access_token': {'write_only': True}}

    def get_fields(self):
        fields = super().get_fields()
        fields['access_token'] = serializers.CharField(write_only=True, required=False, allow_blank=True)
        return fields


# ─── Plans / Subscriptions ────────────────────────────────────────────────────

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'max_leads', 'max_agents', 'max_channels', 'price_monthly']


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ['id', 'plan', 'organization_name', 'status', 'trial_ends_at', 'current_period_end', 'created_at']

    def get_organization_name(self, obj):
        return obj.organization.name
