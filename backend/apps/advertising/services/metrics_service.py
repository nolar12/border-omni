import logging
from datetime import date, timedelta

from apps.advertising.models import AdCampaign, AdMetric
from apps.advertising.providers import GoogleAdsProvider

logger = logging.getLogger('apps')

PROVIDERS = {
    'google_ads': GoogleAdsProvider,
}


class MetricsService:
    """Sincroniza métricas diárias (snapshot) de uma campanha a partir do provider."""

    def sync_campaign_metrics(self, campaign: AdCampaign, days_back: int = 7) -> int:
        if not campaign.external_campaign_id:
            return 0

        provider_cls = PROVIDERS.get(campaign.provider)
        if not provider_cls:
            return 0

        date_to = date.today()
        date_from = date_to - timedelta(days=days_back)
        snapshots = provider_cls().get_metrics(
            campaign.advertising_account, campaign.external_campaign_id, date_from, date_to
        )

        for snap in snapshots:
            AdMetric.objects.update_or_create(
                campaign=campaign,
                date=snap.date,
                defaults={
                    'impressions': snap.impressions,
                    'clicks': snap.clicks,
                    'cost': snap.cost,
                    'ctr': snap.ctr,
                    'average_cpc': snap.average_cpc,
                    'conversions': snap.conversions,
                    'cost_per_conversion': snap.cost_per_conversion,
                },
            )
        return len(snapshots)
