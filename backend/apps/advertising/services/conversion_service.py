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

# Categoria da Conversion Action no Google Ads, por tipo de evento interno —
# usada apenas na primeira vez, quando a ação ainda não existe e precisa ser criada.
EVENT_CATEGORIES = {
    'qualified_lead': 'QUALIFIED_LEAD',
    'reservation': 'LEAD',
    'sale': 'PURCHASE',
}

EVENT_LABELS = {
    'qualified_lead': 'Lead Qualificado',
    'reservation': 'Reserva',
    'sale': 'Venda',
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
        has_ad_click_id = attribution and (attribution.gclid or attribution.gbraid or attribution.wbraid)
        if not has_ad_click_id or not attribution.campaign:
            return

        campaign = attribution.campaign
        provider_cls = PROVIDERS.get(campaign.provider)
        if not provider_cls:
            AdConversionUpload.objects.create(
                organization=organization, ad_event=event, campaign=campaign, gclid=attribution.gclid,
                status='error', error_message=f'Provider "{campaign.provider}" não suportado.',
            )
            return

        try:
            conversion_action = self._ensure_conversion_action(campaign.advertising_account, event.event_type, provider_cls)
        except GoogleAdsProviderError as exc:
            logger.exception('ConversionService: falha ao criar conversion action')
            AdConversionUpload.objects.create(
                organization=organization, ad_event=event, campaign=campaign, gclid=attribution.gclid,
                status='error', error_message=exc.user_message,
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

        try:
            result = provider_cls().upload_conversion(
                campaign.advertising_account,
                ConversionSpec(
                    conversion_action=conversion_action,
                    gclid=attribution.gclid,
                    gbraid=attribution.gbraid,
                    wbraid=attribution.wbraid,
                    conversion_value=float(value) if value is not None else None,
                    event_id=str(upload.event_id),
                    phone=getattr(lead, 'phone', ''),
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

    def _ensure_conversion_action(self, account, event_type: str, provider_cls) -> str:
        """
        Retorna o resource name da Conversion Action para este tipo de evento,
        criando-a automaticamente no provider na primeira vez que for necessária
        (nenhuma configuração manual no Google Ads é exigida do usuário).
        """
        metadata = account.metadata or {}
        conversion_actions = metadata.get('conversion_actions', {})
        existing = conversion_actions.get(event_type)
        if existing:
            return existing

        category = EVENT_CATEGORIES.get(event_type, 'LEAD')
        label = EVENT_LABELS.get(event_type, event_type)
        resource_name = provider_cls().create_conversion_action(account, f'Omni Ads — {label}', category)

        conversion_actions[event_type] = resource_name
        metadata['conversion_actions'] = conversion_actions
        account.metadata = metadata
        account.save(update_fields=['metadata'])
        return resource_name
