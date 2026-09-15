from rest_framework import serializers

from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdMetric, AdvertisingSettings, AdClickToken, AdChatMessage,
    AdCampaignBriefing, AdAgentDecision,
)


class AdvertisingAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvertisingAccount
        fields = [
            'id', 'provider', 'customer_id', 'login_customer_id', 'status',
            'is_active', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class AdMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdMetric
        fields = [
            'id', 'date', 'impressions', 'clicks', 'cost', 'ctr',
            'average_cpc', 'conversions', 'cost_per_conversion',
        ]


class AdCampaignSerializer(serializers.ModelSerializer):
    litter_name = serializers.CharField(source='litter.name', read_only=True, default='')

    class Meta:
        model = AdCampaign
        fields = [
            'id', 'advertising_account', 'litter', 'litter_name', 'provider',
            'external_campaign_id', 'name', 'campaign_type', 'objective',
            'daily_budget', 'total_budget', 'status', 'region', 'radius_km',
            'start_date', 'end_date', 'landing_url', 'ad_headlines',
            'ad_descriptions', 'ad_keywords', 'client_request_id',
            'error_message', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'external_campaign_id', 'status', 'error_message',
            'created_at', 'updated_at',
        ]


class AdCampaignDetailSerializer(AdCampaignSerializer):
    metrics = AdMetricSerializer(many=True, read_only=True)

    class Meta(AdCampaignSerializer.Meta):
        fields = AdCampaignSerializer.Meta.fields + ['metrics']


class AdvertisingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvertisingSettings
        fields = [
            'is_enabled', 'send_qualified_events', 'send_reservation_events',
            'send_sale_events', 'default_daily_budget', 'max_auto_budget_change_percent', 'updated_at',
        ]
        read_only_fields = ['updated_at']


class PublicAdClickTokenRequestSerializer(serializers.Serializer):
    org_id = serializers.IntegerField()
    gclid = serializers.CharField(required=False, allow_blank=True, default='')
    gbraid = serializers.CharField(required=False, allow_blank=True, default='')
    wbraid = serializers.CharField(required=False, allow_blank=True, default='')
    utm_source = serializers.CharField(required=False, allow_blank=True, default='')
    utm_medium = serializers.CharField(required=False, allow_blank=True, default='')
    utm_campaign = serializers.CharField(required=False, allow_blank=True, default='')
    utm_content = serializers.CharField(required=False, allow_blank=True, default='')
    ad_group_id = serializers.CharField(required=False, allow_blank=True, default='')
    ad_id = serializers.CharField(required=False, allow_blank=True, default='')
    keyword = serializers.CharField(required=False, allow_blank=True, default='')
    search_term = serializers.CharField(required=False, allow_blank=True, default='')
    litter_id = serializers.IntegerField(required=False, allow_null=True)


class AdClickTokenResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdClickToken
        fields = ['token']


class AdChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdChatMessage
        fields = ['id', 'role', 'content', 'actions_taken', 'created_at']
        read_only_fields = fields


class AdCampaignBriefingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdCampaignBriefing
        fields = [
            'product_description', 'objective', 'deadline', 'price_info',
            'primary_conversion', 'priority_regions', 'positive_intent_keywords',
            'negative_keywords', 'do_not_negate_keywords', 'notes', 'updated_at',
        ]
        read_only_fields = ['updated_at']


class AdAgentDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdAgentDecision
        fields = [
            'id', 'action', 'before', 'after', 'reason', 'hypothesis',
            'metrics_snapshot', 'performed_by', 'approval_status', 'created_at',
        ]
        read_only_fields = fields
