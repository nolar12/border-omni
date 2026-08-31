from rest_framework import serializers

from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdMetric, AdvertisingSettings, AdClickToken,
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
            'send_sale_events', 'default_daily_budget', 'updated_at',
        ]
        read_only_fields = ['updated_at']


class PublicAdClickTokenRequestSerializer(serializers.Serializer):
    org_id = serializers.IntegerField()
    gclid = serializers.CharField(required=False, allow_blank=True, default='')
    utm_source = serializers.CharField(required=False, allow_blank=True, default='')
    utm_medium = serializers.CharField(required=False, allow_blank=True, default='')
    utm_campaign = serializers.CharField(required=False, allow_blank=True, default='')
    utm_content = serializers.CharField(required=False, allow_blank=True, default='')
    litter_id = serializers.IntegerField(required=False, allow_null=True)


class AdClickTokenResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdClickToken
        fields = ['token']
