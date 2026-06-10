from django.contrib.auth.models import User
from rest_framework import serializers
from apps.core.models import Organization, UserProfile, Plan, Subscription, AgentConfig, InitialMessageMedia, GalleryMedia
from apps.leads.models import Lead, LeadTag, Note, LeadProfile
from apps.conversations.models import Message, Conversation, MessageTemplate
from apps.quick_replies.models import QuickReply, QuickReplyCategory
from apps.channels.models import ChannelProvider, QualityRatingEvent, MetaConversionEvent
from apps.contracts.models import SaleContract
from apps.notes.models import GenericNote
from apps.kennel.models import (
    Dog, Litter, DogMedia, LitterMedia, DogHealthRecord, LitterHealthRecord,
    LitterDocumentTemplate, LitterRegistrationDocument,
)


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    kennel_cbkc_code = serializers.SerializerMethodField()
    kennel_fci_code = serializers.SerializerMethodField()
    kennel_prefix = serializers.SerializerMethodField()
    kennel_owner_name = serializers.SerializerMethodField()
    kennel_address_line = serializers.SerializerMethodField()
    kennel_neighborhood = serializers.SerializerMethodField()
    kennel_city = serializers.SerializerMethodField()
    kennel_state = serializers.SerializerMethodField()
    kennel_zip_code = serializers.SerializerMethodField()
    kennel_phone = serializers.SerializerMethodField()
    kennel_breed = serializers.SerializerMethodField()
    kennel_registry_date = serializers.SerializerMethodField()
    kennel_issue_date = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'organization_name', 'plan_name',
            'phone',
            'kennel_cbkc_code', 'kennel_fci_code', 'kennel_prefix', 'kennel_owner_name',
            'kennel_address_line', 'kennel_neighborhood', 'kennel_city', 'kennel_state',
            'kennel_zip_code', 'kennel_phone', 'kennel_breed',
            'kennel_registry_date', 'kennel_issue_date',
        ]

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

    def get_phone(self, obj):
        try:
            return obj.profile.phone
        except Exception:
            return ''

    def _profile_value(self, obj, field_name, default=''):
        try:
            value = getattr(obj.profile, field_name, default)
            return value if value is not None else default
        except Exception:
            return default

    def get_kennel_cbkc_code(self, obj):
        return self._profile_value(obj, 'kennel_cbkc_code')

    def get_kennel_fci_code(self, obj):
        return self._profile_value(obj, 'kennel_fci_code')

    def get_kennel_prefix(self, obj):
        return self._profile_value(obj, 'kennel_prefix')

    def get_kennel_owner_name(self, obj):
        return self._profile_value(obj, 'kennel_owner_name')

    def get_kennel_address_line(self, obj):
        return self._profile_value(obj, 'kennel_address_line')

    def get_kennel_neighborhood(self, obj):
        return self._profile_value(obj, 'kennel_neighborhood')

    def get_kennel_city(self, obj):
        return self._profile_value(obj, 'kennel_city')

    def get_kennel_state(self, obj):
        return self._profile_value(obj, 'kennel_state')

    def get_kennel_zip_code(self, obj):
        return self._profile_value(obj, 'kennel_zip_code')

    def get_kennel_phone(self, obj):
        return self._profile_value(obj, 'kennel_phone')

    def get_kennel_breed(self, obj):
        return self._profile_value(obj, 'kennel_breed')

    def get_kennel_registry_date(self, obj):
        value = self._profile_value(obj, 'kennel_registry_date', None)
        return value.isoformat() if value else None

    def get_kennel_issue_date(self, obj):
        value = self._profile_value(obj, 'kennel_issue_date', None)
        return value.isoformat() if value else None


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

class LeadProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadProfile
        fields = [
            'intencao_uso', 'perfil_localizacao', 'potencial_compra',
            'sensibilidade_preco', 'urgencia', 'classificacao_motivo',
            'tags_automaticas', 'is_reserved', 'is_purchased', 'updated_at',
        ]


class MetaConversionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetaConversionEvent
        fields = [
            'id', 'event_name', 'lead_status', 'status',
            'campaign_id', 'adset_id', 'ad_id',
            'error_message', 'sent_at', 'created_at',
        ]


class AssignedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']


class LeadListSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    assigned_to = AssignedUserSerializer(read_only=True)
    last_message_direction = serializers.SerializerMethodField()
    lead_classification = serializers.CharField(read_only=True)
    whatsapp_last_message_at = serializers.SerializerMethodField()
    last_message_text = serializers.SerializerMethodField()
    awaiting_human_reply = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id', 'phone', 'full_name', 'city', 'state', 'tier', 'score',
            'lead_classification', 'status', 'source', 'channels_used', 'is_ai_active',
            'is_archived', 'opted_in', 'lgpd_consent', 'assigned_to', 'tags',
            'last_message_direction', 'whatsapp_last_message_at', 'last_message_text',
            'awaiting_human_reply', 'created_at', 'updated_at',
        ]

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))

    def get_last_message_direction(self, obj):
        # Lê do atributo anotado pelo LeadViewSet (elimina N+1).
        # Fallback via query para contextos onde a annotation não está presente.
        val = getattr(obj, '_last_msg_direction', None)
        if val is not None:
            return val
        try:
            msg = Message.objects.filter(
                conversation__lead=obj
            ).order_by('-created_at').first()
            return msg.direction if msg else None
        except Exception:
            return None

    def get_whatsapp_last_message_at(self, obj):
        val = getattr(obj, '_whatsapp_last_msg_at', None)
        if val is not None:
            return val.isoformat() if hasattr(val, 'isoformat') else val
        try:
            conv = obj.conversations.filter(channel='whatsapp').order_by('-last_message_at').first()
            if conv and conv.last_message_at:
                return conv.last_message_at.isoformat()
            return None
        except Exception:
            return None

    def get_last_message_text(self, obj):
        val = getattr(obj, '_last_msg_text', None)
        if val is not None:
            return val
        try:
            msg = Message.objects.filter(
                conversation__lead=obj
            ).order_by('-created_at').first()
            return msg.text if msg else None
        except Exception:
            return None

    def get_awaiting_human_reply(self, obj):
        """
        True quando o lead enviou uma mensagem que ainda não foi respondida
        por um humano (mensagens automáticas/bot não contam como resposta humana).
        Usa atributos anotados pelo LeadViewSet para evitar N+1 queries.
        """
        last_in = getattr(obj, '_last_in_at', None)
        if last_in is None:
            # Fallback via query para contextos sem annotation
            try:
                msgs = list(
                    Message.objects.filter(conversation__lead=obj)
                    .order_by('-created_at')
                    .values('direction', 'provider_message_id', 'created_at')[:20]
                )
                last_in_msg = next((m for m in msgs if m['direction'] == 'IN'), None)
                if not last_in_msg:
                    return False
                last_human_out = next(
                    (m for m in msgs if m['direction'] == 'OUT' and m['provider_message_id']),
                    None,
                )
                if not last_human_out:
                    return True
                return last_in_msg['created_at'] > last_human_out['created_at']
            except Exception:
                return False
        if not last_in:
            return False
        last_human_out = getattr(obj, '_last_human_out_at', None)
        if not last_human_out:
            return True
        return last_in > last_human_out


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ['id', 'channel', 'state', 'last_message_at', 'created_at']


class LeadDetailSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    notes = NoteSerializer(many=True, read_only=True)
    assigned_to = AssignedUserSerializer(read_only=True)
    conversations = ConversationSerializer(many=True, read_only=True)
    profile = LeadProfileSerializer(read_only=True)
    last_meta_event = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id', 'phone', 'facebook_psid', 'instagram_user_id',
            'full_name', 'instagram_handle', 'city', 'state',
            'housing_type', 'daily_time_minutes', 'experience_level', 'budget_ok',
            'timeline', 'purpose', 'has_kids', 'has_other_pets', 'score', 'tier',
            'lead_classification', 'is_archived', 'opted_in', 'lgpd_consent',
            'status', 'source', 'channels_used', 'is_ai_active', 'assigned_to',
            'conversation_state', 'tags', 'notes', 'conversations',
            'ad_referral', 'ctwa_clid',
            'profile', 'last_meta_event',
            'created_at', 'updated_at',
        ]

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))

    def get_last_meta_event(self, obj):
        try:
            ev = obj.meta_events.order_by('-created_at').first()
            return MetaConversionEventSerializer(ev).data if ev else None
        except Exception:
            return None


# ─── Messages ────────────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'direction', 'text', 'provider_message_id', 'msg_status', 'created_at']


# ─── Quick Replies ────────────────────────────────────────────────────────────

class QuickReplyCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickReplyCategory
        fields = ['id', 'name', 'sort_order', 'created_at']
        read_only_fields = ['created_at']


class QuickReplySerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    is_personal = serializers.SerializerMethodField()

    class Meta:
        model = QuickReply
        fields = [
            'id',
            'category_ref', 'category_name',
            'title', 'body',
            # legacy fields kept for backward compat
            'category', 'text', 'shortcut',
            'sort_order', 'is_personal', 'is_active', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_category_name(self, obj):
        if obj.category_ref:
            return obj.category_ref.name
        return obj.get_category_display() or ''

    def get_is_personal(self, obj):
        return obj.user_id is not None


# ─── Channels ────────────────────────────────────────────────────────────────

class ChannelProviderSerializer(serializers.ModelSerializer):
    access_token_masked = serializers.SerializerMethodField()

    class Meta:
        model = ChannelProvider
        fields = [
            'id', 'name', 'provider', 'app_id', 'app_secret',
            'access_token', 'access_token_masked',
            'phone_number_id', 'business_account_id',
            'instagram_account_id', 'page_id',
            'webhook_verify_token', 'webhook_url',
            'quality_rating', 'quality_synced_at',
            'is_active', 'is_simulated', 'verification_status',
            'last_verified_at', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'access_token': {'write_only': True, 'required': False, 'allow_blank': True},
            'app_secret': {'write_only': True, 'required': False, 'allow_blank': True},
        }

    def get_access_token_masked(self, obj):
        if not obj.access_token:
            return ''
        token = obj.access_token
        if len(token) <= 12:
            return '••••••••'
        return token[:6] + '••••••••' + token[-4:]


class QualityRatingEventSerializer(serializers.ModelSerializer):
    is_degradation = serializers.BooleanField(read_only=True)

    class Meta:
        model = QualityRatingEvent
        fields = ['id', 'previous_rating', 'new_rating', 'is_degradation', 'created_at']


# ─── Agent Config ────────────────────────────────────────────────────────────

class AgentConfigSerializer(serializers.ModelSerializer):
    openai_api_key_masked = serializers.SerializerMethodField()

    class Meta:
        model = AgentConfig
        fields = [
            'id', 'model', 'system_prompt', 'temperature',
            'rag_enabled', 'match_threshold', 'match_count',
            'max_history_messages', 'openai_api_key', 'openai_api_key_masked',
            'cordiality_enabled', 'cordiality_use_ai',
            'bot_enabled', 'initial_message', 'sequence_message', 'link_message',
            'conversation_template', 'use_conversation_template',
            'off_hours_enabled', 'off_hours_start', 'off_hours_end',
            'off_hours_message', 'off_hours_timezone',
            'updated_at',
        ]
        extra_kwargs = {
            'openai_api_key': {'write_only': True, 'required': False, 'allow_blank': True},
        }

    def get_openai_api_key_masked(self, obj):
        if not obj.openai_api_key:
            return ''
        k = obj.openai_api_key
        if len(k) <= 12:
            return '••••••••'
        return k[:8] + '••••••••' + k[-4:]


# ─── Initial Message Media ───────────────────────────────────────────────────

class InitialMessageMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = InitialMessageMedia
        fields = ['id', 'url', 'media_type', 'original_name', 'order', 'created_at']
        read_only_fields = ['id', 'url', 'media_type', 'original_name', 'created_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


# ─── Message Templates ───────────────────────────────────────────────────────

class MessageTemplateSerializer(serializers.ModelSerializer):
    channel_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    variable_count = serializers.SerializerMethodField()
    header_type_display = serializers.SerializerMethodField()

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'name', 'language', 'category', 'status', 'status_display',
            'header_type', 'header_type_display', 'header_text', 'header_media_url',
            'body_text', 'footer_text',
            'meta_template_id', 'rejection_reason',
            'channel', 'channel_name',
            'variable_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'meta_template_id', 'status', 'rejection_reason', 'created_at', 'updated_at']

    def get_channel_name(self, obj):
        return obj.channel.name if obj.channel else ''

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_header_type_display(self, obj):
        return obj.get_header_type_display()

    def get_variable_count(self, obj):
        import re
        matches = re.findall(r'\{\{\d+\}\}', obj.body_text)
        return len(set(matches))


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


class GalleryMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = GalleryMedia
        fields = ['id', 'name', 'description', 'file_url', 'mime_type', 'media_type', 'size_bytes', 'created_at']
        read_only_fields = ['id', 'file_url', 'mime_type', 'media_type', 'size_bytes', 'created_at']

    def get_file_url(self, obj):
        """Resolve caminhos relativos (/media/...) para URL absoluta do S3 ou API."""
        from django.conf import settings as django_settings
        url = obj.file_url or ''
        if url.startswith('http'):
            return url
        media_base = (getattr(django_settings, 'MEDIA_BASE_URL', '') or '').rstrip('/')
        if media_base:
            return f'{media_base}{url}'
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url


# ─── Contracts ───────────────────────────────────────────────────────────────

class ContractSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()
    puppy_sex_display = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    lead_phone = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    dog_name = serializers.SerializerMethodField()

    class Meta:
        model = SaleContract
        fields = [
            'id', 'lead', 'lead_name', 'lead_phone',
            'dog', 'dog_name',
            'puppy_sex', 'puppy_sex_display', 'puppy_color', 'puppy_microchip',
            'puppy_father', 'puppy_mother', 'puppy_birth_date',
            'price', 'deposit_amount',
            'buyer_name', 'buyer_cpf', 'buyer_marital_status',
            'buyer_address', 'buyer_cep', 'buyer_email',
            'status', 'status_display', 'token',
            'signature_data', 'signature_type',
            'pdf_url',
            'created_at', 'updated_at', 'buyer_filled_at', 'approved_at', 'signed_at',
        ]
        read_only_fields = [
            'id', 'token', 'price', 'deposit_amount', 'status_display', 'puppy_sex_display',
            'lead_name', 'lead_phone', 'dog_name', 'pdf_url',
            'created_at', 'updated_at', 'buyer_filled_at', 'approved_at', 'signed_at',
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_puppy_sex_display(self, obj):
        return obj.get_puppy_sex_display()

    def get_lead_name(self, obj):
        if obj.lead:
            return obj.lead.full_name or obj.lead.phone
        return ''

    def get_lead_phone(self, obj):
        if obj.lead:
            return obj.lead.phone
        return ''

    def get_dog_name(self, obj):
        if obj.dog:
            return obj.dog.name
        return ''

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None


class ContractPublicSerializer(serializers.ModelSerializer):
    """Serializer restrito para a página pública (sem dados sensíveis da organização)."""
    status_display = serializers.SerializerMethodField()
    puppy_sex_display = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    deposit_display = serializers.SerializerMethodField()
    balance_display = serializers.SerializerMethodField()

    class Meta:
        model = SaleContract
        fields = [
            'id', 'token',
            'puppy_sex', 'puppy_sex_display', 'puppy_color', 'puppy_microchip',
            'puppy_father', 'puppy_mother', 'puppy_birth_date',
            'price', 'deposit_amount',
            'price_display', 'deposit_display', 'balance_display',
            'buyer_name', 'buyer_cpf', 'buyer_marital_status',
            'buyer_address', 'buyer_cep', 'buyer_email',
            'status', 'status_display',
            'created_at',
        ]
        read_only_fields = fields

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_puppy_sex_display(self, obj):
        return obj.get_puppy_sex_display()

    def _fmt_brl(self, value):
        if value is None:
            return '—'
        try:
            v = float(value)
            return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            return str(value)

    def get_price_display(self, obj):
        return self._fmt_brl(obj.price)

    def get_deposit_display(self, obj):
        return self._fmt_brl(obj.deposit_amount)

    def get_balance_display(self, obj):
        if obj.price is None or obj.deposit_amount is None:
            return '—'
        return self._fmt_brl(obj.price - obj.deposit_amount)


# ─── Generic Notes ────────────────────────────────────────────────────────────

class GenericNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = GenericNote
        fields = [
            'id', 'title', 'content', 'color', 'is_pinned',
            'author_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'author_name', 'created_at', 'updated_at']

    def get_author_name(self, obj):
        if obj.author:
            return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.email
        return 'Sistema'


# ─── Kennel ───────────────────────────────────────────────────────────────────

class DogMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DogMedia
        fields = ['id', 'file', 'file_url', 'caption', 'uploaded_at']
        read_only_fields = ['id', 'file_url', 'uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class LitterMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LitterMedia
        fields = ['id', 'file', 'file_url', 'caption', 'uploaded_at']
        read_only_fields = ['id', 'file_url', 'uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class DogHealthRecordSerializer(serializers.ModelSerializer):
    record_type_display = serializers.SerializerMethodField()

    class Meta:
        model = DogHealthRecord
        fields = [
            'id', 'dog', 'record_type', 'record_type_display',
            'description', 'date', 'next_date', 'vet', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'record_type_display', 'created_at']

    def get_record_type_display(self, obj):
        return obj.get_record_type_display()


class LitterHealthRecordSerializer(serializers.ModelSerializer):
    record_type_display = serializers.SerializerMethodField()

    class Meta:
        model = LitterHealthRecord
        fields = [
            'id', 'litter', 'record_type', 'record_type_display',
            'description', 'date', 'next_date', 'vet', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'record_type_display', 'created_at']

    def get_record_type_display(self, obj):
        return obj.get_record_type_display()


class DogListSerializer(serializers.ModelSerializer):
    sex_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    father_name = serializers.SerializerMethodField()
    mother_name = serializers.SerializerMethodField()

    class Meta:
        model = Dog
        fields = [
            'id', 'name', 'breed', 'sex', 'sex_display', 'birth_date',
            'color', 'pedigree_number', 'microchip',
            'status', 'status_display', 'price',
            'father_name', 'mother_name', 'origin_litter',
            'cover_photo', 'created_at', 'updated_at',
        ]

    def get_sex_display(self, obj):
        return obj.get_sex_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_cover_photo(self, obj):
        first = obj.media.first()
        if first:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first.file.url)
            return first.file.url
        return None

    def get_father_name(self, obj):
        return obj.father.name if obj.father else ''

    def get_mother_name(self, obj):
        return obj.mother.name if obj.mother else ''


class DogDetailSerializer(DogListSerializer):
    media = DogMediaSerializer(many=True, read_only=True)
    health_records = DogHealthRecordSerializer(many=True, read_only=True)

    class Meta(DogListSerializer.Meta):
        fields = DogListSerializer.Meta.fields + [
            'tattoo', 'notes', 'media', 'health_records',
        ]


class LitterListSerializer(serializers.ModelSerializer):
    father_name = serializers.SerializerMethodField()
    mother_name = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    total_count = serializers.SerializerMethodField()

    class Meta:
        model = Litter
        fields = [
            'id', 'name', 'father', 'father_name', 'mother', 'mother_name',
            'mating_date', 'expected_birth_date', 'birth_date',
            'male_count', 'female_count', 'total_count',
            'cbkc_number', 'is_featured', 'cover_photo', 'created_at', 'updated_at',
        ]

    def get_father_name(self, obj):
        return obj.father.name if obj.father else ''

    def get_mother_name(self, obj):
        return obj.mother.name if obj.mother else ''

    def get_cover_photo(self, obj):
        first = obj.media.first()
        if first:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first.file.url)
            return first.file.url
        return None

    def get_total_count(self, obj):
        return obj.male_count + obj.female_count


class DogWithMediaSerializer(DogListSerializer):
    """DogListSerializer + media, used to embed puppies inside LitterDetailSerializer."""
    media = DogMediaSerializer(many=True, read_only=True)

    class Meta(DogListSerializer.Meta):
        fields = DogListSerializer.Meta.fields + ['notes', 'media']


class LitterDetailSerializer(LitterListSerializer):
    puppies = DogWithMediaSerializer(many=True, read_only=True)
    media = LitterMediaSerializer(many=True, read_only=True)
    health_records = LitterHealthRecordSerializer(many=True, read_only=True)

    class Meta(LitterListSerializer.Meta):
        fields = LitterListSerializer.Meta.fields + [
            'notes', 'puppies', 'media', 'health_records',
        ]


class LitterDocumentTemplateSerializer(serializers.ModelSerializer):
    source_file_url = serializers.SerializerMethodField()

    class Meta:
        model = LitterDocumentTemplate
        fields = [
            'id', 'name', 'source_file', 'source_file_url',
            'field_mapping', 'required_fields', 'field_inventory',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'field_inventory', 'source_file_url', 'created_at', 'updated_at']

    def get_source_file_url(self, obj):
        request = self.context.get('request')
        if obj.source_file and request:
            return request.build_absolute_uri(obj.source_file.url)
        return obj.source_file.url if obj.source_file else None


class LitterRegistrationDocumentSerializer(serializers.ModelSerializer):
    generated_file_url = serializers.SerializerMethodField()
    template_name = serializers.SerializerMethodField()
    litter_name = serializers.SerializerMethodField()

    class Meta:
        model = LitterRegistrationDocument
        fields = [
            'id', 'litter', 'litter_name', 'template', 'template_name',
            'extra_data', 'generated_file', 'generated_file_url',
            'status', 'error_message', 'generated_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'litter_name', 'template_name',
            'generated_file', 'generated_file_url',
            'status', 'error_message', 'generated_at',
            'created_at', 'updated_at',
        ]

    def get_generated_file_url(self, obj):
        request = self.context.get('request')
        if obj.generated_file and request:
            return request.build_absolute_uri(obj.generated_file.url)
        return obj.generated_file.url if obj.generated_file else None

    def get_template_name(self, obj):
        return obj.template.name if obj.template else ''

    def get_litter_name(self, obj):
        return obj.litter.name if obj.litter else ''


# ─── Public (no auth) ─────────────────────────────────────────────────────────

class PublicPuppySerializer(serializers.ModelSerializer):
    sex_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    media = DogMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Dog
        fields = [
            'id', 'name', 'sex', 'sex_display',
            'birth_date', 'color',
            'status', 'status_display',
            'notes',
            'media',
        ]

    def get_sex_display(self, obj):
        return obj.get_sex_display()

    def get_status_display(self, obj):
        return obj.get_status_display()


class PublicLitterSerializer(serializers.ModelSerializer):
    father_name = serializers.SerializerMethodField()
    mother_name = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    total_count = serializers.SerializerMethodField()
    puppies = PublicPuppySerializer(many=True, read_only=True)
    media = LitterMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Litter
        fields = [
            'id', 'name', 'is_featured',
            'father_name', 'mother_name',
            'birth_date', 'expected_birth_date',
            'male_count', 'female_count', 'total_count',
            'cover_photo', 'puppies', 'media',
        ]

    def get_father_name(self, obj):
        return obj.father.name if obj.father else ''

    def get_mother_name(self, obj):
        return obj.mother.name if obj.mother else ''

    def get_cover_photo(self, obj):
        first = obj.media.first()
        if first:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first.file.url)
            return first.file.url
        return None

    def get_total_count(self, obj):
        return obj.male_count + obj.female_count
