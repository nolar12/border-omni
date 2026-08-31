from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Organization
from apps.leads.models import Lead
from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdLeadAttribution, AdvertisingSettings, AdEvent, AdConversionUpload,
)
from apps.advertising.providers.base import ProviderResult
from apps.advertising.services.conversion_service import ConversionService


class ConversionServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil F')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='5556667777')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp', daily_budget=10,
            external_campaign_id='ext-1',
        )
        self.lead = Lead.objects.create(organization=self.org, phone='554899991111')

    def test_page_view_never_creates_conversion_upload(self):
        ConversionService().record_event(organization=self.org, lead=self.lead, event_type='page_view')
        self.assertEqual(AdEvent.objects.filter(event_type='page_view').count(), 1)
        self.assertEqual(AdConversionUpload.objects.count(), 0)

    def test_qualified_lead_skips_upload_without_attribution(self):
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=True)
        ConversionService().record_event(organization=self.org, lead=self.lead, event_type='qualified_lead')
        self.assertEqual(AdConversionUpload.objects.count(), 0)

    def test_qualified_lead_skips_upload_when_settings_disabled(self):
        AdLeadAttribution.objects.create(lead=self.lead, campaign=self.campaign, gclid='gclid-1')
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=False)
        ConversionService().record_event(organization=self.org, lead=self.lead, event_type='qualified_lead')
        self.assertEqual(AdConversionUpload.objects.count(), 0)

    def test_qualified_lead_skipped_without_conversion_action_mapping(self):
        AdLeadAttribution.objects.create(lead=self.lead, campaign=self.campaign, gclid='gclid-1')
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=True)
        ConversionService().record_event(organization=self.org, lead=self.lead, event_type='qualified_lead')
        upload = AdConversionUpload.objects.get()
        self.assertEqual(upload.status, 'skipped')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.upload_conversion')
    def test_qualified_lead_uploads_when_fully_configured(self, mock_upload):
        mock_upload.return_value = ProviderResult(success=True, raw={'ok': True})
        self.account.metadata = {'conversion_actions': {'qualified_lead': 'customers/1/conversionActions/1'}}
        self.account.save(update_fields=['metadata'])
        AdLeadAttribution.objects.create(lead=self.lead, campaign=self.campaign, gclid='gclid-1')
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=True)

        ConversionService().record_event(organization=self.org, lead=self.lead, event_type='qualified_lead')

        upload = AdConversionUpload.objects.get()
        self.assertEqual(upload.status, 'sent')
        mock_upload.assert_called_once()
