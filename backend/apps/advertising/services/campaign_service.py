import logging

from django.conf import settings

from apps.advertising.models import AdCampaign
from apps.advertising.providers import GoogleAdsProvider, GoogleAdsProviderError
from apps.advertising.providers.base import CampaignSpec

logger = logging.getLogger('apps')

PROVIDERS = {
    'google_ads': GoogleAdsProvider,
}


class CampaignService:
    """
    Orquestra a criação/atualização/pausa/retomada de campanhas, delegando a
    operação real de escrita ao AdvertisingProvider do respectivo provider.

    Pensada para ser chamável tanto pela view HTTP quanto, futuramente, por um
    agente de IA (ex.: CampaignService().pause_campaign(org, campaign_id)) sem
    que o chamador precise conhecer o provider ou o model diretamente.
    """

    def _provider(self, provider_name: str):
        provider_cls = PROVIDERS.get(provider_name)
        if not provider_cls:
            raise GoogleAdsProviderError(f'Provider "{provider_name}" não suportado.', code='unsupported_provider')
        return provider_cls()

    def create_campaign(self, *, organization, advertising_account, litter, data: dict, client_request_id: str | None = None) -> AdCampaign:
        if client_request_id:
            existing = AdCampaign.objects.filter(client_request_id=client_request_id).first()
            if existing:
                return existing

        campaign = AdCampaign.objects.create(
            organization=organization,
            advertising_account=advertising_account,
            litter=litter,
            provider=advertising_account.provider,
            name=data['name'],
            daily_budget=data['daily_budget'],
            total_budget=data.get('total_budget'),
            region=data.get('region', ''),
            radius_km=data.get('radius_km'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            landing_url=data.get('landing_url', ''),
            ad_headlines=data.get('ad_headlines', []),
            ad_descriptions=data.get('ad_descriptions', []),
            ad_keywords=data.get('ad_keywords', []),
            client_request_id=client_request_id,
            status='pending',
        )

        if not settings.GOOGLE_ADS_ENABLED:
            campaign.status = 'draft'
            campaign.error_message = 'Omni Ads está desabilitado neste ambiente (GOOGLE_ADS_ENABLED=False).'
            campaign.save(update_fields=['status', 'error_message'])
            return campaign

        spec = CampaignSpec(
            name=campaign.name,
            daily_budget=float(campaign.daily_budget),
            region=campaign.region,
            radius_km=campaign.radius_km,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            landing_url=campaign.landing_url,
            headlines=campaign.ad_headlines,
            descriptions=campaign.ad_descriptions,
            keywords=campaign.ad_keywords,
        )
        try:
            provider = self._provider(advertising_account.provider)
            result = provider.create_campaign(advertising_account, spec)
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.create_campaign failed')
            campaign.status = 'error'
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['status', 'error_message'])
            return campaign

        campaign.external_campaign_id = result.external_id
        campaign.status = 'active'
        campaign.error_message = result.error_message
        campaign.save(update_fields=['external_campaign_id', 'status', 'error_message'])
        return campaign

    def pause_campaign(self, organization, campaign_id: int) -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        try:
            self._provider(campaign.provider).pause_campaign(campaign.advertising_account, campaign.external_campaign_id)
            campaign.status = 'paused'
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.pause_campaign failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['status', 'error_message'])
        return campaign

    def resume_campaign(self, organization, campaign_id: int) -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        try:
            self._provider(campaign.provider).resume_campaign(campaign.advertising_account, campaign.external_campaign_id)
            campaign.status = 'active'
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.resume_campaign failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['status', 'error_message'])
        return campaign

    def update_daily_budget(self, organization, campaign_id: int, new_daily_budget: float) -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        try:
            spec = CampaignSpec(name=campaign.name, daily_budget=float(new_daily_budget))
            self._provider(campaign.provider).update_campaign(campaign.advertising_account, campaign.external_campaign_id, spec)
            campaign.daily_budget = new_daily_budget
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_daily_budget failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['daily_budget', 'error_message'])
        return campaign
