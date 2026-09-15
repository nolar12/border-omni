import logging
from datetime import date, timedelta

from django.db.models import Sum

from apps.advertising.models import AdCampaign, AdMetric
from apps.advertising.providers import GoogleAdsProvider
from apps.advertising.services import lead_funnel_service

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

    def build_snapshot(self, campaign: AdCampaign, days_back: int = 30) -> dict:
        """
        Fotografia real do estado da campanha (Google Ads + CRM) no momento em que
        uma decisão é tomada — nunca inventado, só o que já está armazenado
        (AdMetric via sync_campaign_metrics + funil comercial do CRM).
        """
        date_from = date.today() - timedelta(days=days_back)
        agg = AdMetric.objects.filter(campaign=campaign, date__gte=date_from).aggregate(
            cost=Sum('cost'), impressions=Sum('impressions'),
            clicks=Sum('clicks'), conversions=Sum('conversions'),
        )
        cost = float(agg['cost'] or 0)
        impressions = int(agg['impressions'] or 0)
        clicks = int(agg['clicks'] or 0)
        conversions = int(agg['conversions'] or 0)

        funnel = lead_funnel_service.funnel_summary(campaign)
        stages = funnel['stages']
        qualified = stages['QUALIFIED'] + stages['NEGOTIATING'] + stages['RESERVED'] + stages['SOLD']
        reservations = stages['RESERVED'] + stages['SOLD']
        sales = stages['SOLD']
        total_leads = funnel['total_leads']

        def _safe_div(numerator, denominator):
            return round(numerator / denominator, 2) if denominator else None

        return {
            'period_days': days_back,
            'period_from': date_from.isoformat(),
            'period_to': date.today().isoformat(),
            'campaign_id': campaign.id,
            'external_campaign_id': campaign.external_campaign_id,
            'cost': cost,
            'impressions': impressions,
            'clicks': clicks,
            'ctr': _safe_div(clicks, impressions),
            'average_cpc': _safe_div(cost, clicks),
            'conversions': conversions,
            'conversion_rate': _safe_div(conversions, clicks),
            'total_leads': total_leads,
            'cost_per_lead': _safe_div(cost, total_leads),
            'qualified_leads': qualified,
            'cost_per_qualified_lead': _safe_div(cost, qualified),
            'negotiations': stages['NEGOTIATING'],
            'reservations': reservations,
            'sales': sales,
            'cac': _safe_div(cost, sales),
        }
