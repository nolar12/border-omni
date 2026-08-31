import logging

from apps.advertising.models import AdEvent, AdConversionUpload, AdvertisingSettings
from apps.advertising.providers import GoogleAdsProvider, GoogleAdsProviderError
from apps.advertising.providers.base import ConversionSpec

logger = logging.getLogger('apps')

# Quais eventos podem virar conversão enviada ao provider, e qual toggle de
# AdvertisingSettings controla cada um.
UPLOADABLE_EVENTS = {
    'qualified_lead': 'send_qualified_events',
    'reservation': 'send_reservation_events',
    'sale': 'send_sale_events',
}

PROVIDERS = {
    'google_ads': GoogleAdsProvider,
}


class ConversionService:
    """
    Espelha o padrão de apps/channels/meta_conversions_service.py::MetaConversionsService,
    mas separando explicitamente o evento interno (AdEvent, sempre gravado) da conversão
    efetivamente enviada ao provider (AdConversionUpload, condicional).
    """

    def record_event(self, *, organization, lead, event_type: str, metadata: dict | None = None, value=None) -> AdEvent:
        event = AdEvent.objects.create(
            organization=organization,
            lead=lead,
            campaign=getattr(getattr(lead, 'ad_attribution', None), 'campaign', None),
            event_type=event_type,
            metadata=metadata or {},
        )

        self._maybe_upload_conversion(organization=organization, lead=lead, event=event, value=value)
        return event

    def _maybe_upload_conversion(self, *, organization, lead, event: AdEvent, value=None):
        toggle_field = UPLOADABLE_EVENTS.get(event.event_type)
        if not toggle_field:
            return  # evento puramente interno (page_view, whatsapp_click, lead_created)

        ad_settings = AdvertisingSettings.objects.filter(organization=organization).first()
        if not ad_settings or not ad_settings.is_enabled or not getattr(ad_settings, toggle_field):
            return

        attribution = getattr(lead, 'ad_attribution', None)
        if not attribution or not attribution.gclid or not attribution.campaign:
            return

        campaign = attribution.campaign
        conversion_action = (campaign.advertising_account.metadata or {}).get('conversion_actions', {}).get(event.event_type)
        if not conversion_action:
            AdConversionUpload.objects.create(
                organization=organization,
                ad_event=event,
                campaign=campaign,
                gclid=attribution.gclid,
                status='skipped',
                error_message='Nenhuma conversion_action configurada para este tipo de evento.',
            )
            return

        upload = AdConversionUpload.objects.create(
            organization=organization,
            ad_event=event,
            campaign=campaign,
            gclid=attribution.gclid,
            conversion_action=conversion_action,
            conversion_value=value,
            status='pending',
        )

        provider_cls = PROVIDERS.get(campaign.provider)
        if not provider_cls:
            upload.status = 'error'
            upload.error_message = f'Provider "{campaign.provider}" não suportado.'
            upload.save(update_fields=['status', 'error_message'])
            return

        try:
            result = provider_cls().upload_conversion(
                campaign.advertising_account,
                ConversionSpec(
                    conversion_action=conversion_action,
                    gclid=attribution.gclid,
                    conversion_value=float(value) if value is not None else None,
                    event_id=str(upload.event_id),
                ),
            )
        except GoogleAdsProviderError as exc:
            logger.exception('ConversionService upload_conversion failed')
            upload.status = 'error'
            upload.error_message = exc.user_message
            upload.save(update_fields=['status', 'error_message'])
            return

        upload.response = result.raw
        upload.status = 'sent' if result.success else 'error'
        upload.error_message = result.error_message
        upload.save(update_fields=['response', 'status', 'error_message'])
