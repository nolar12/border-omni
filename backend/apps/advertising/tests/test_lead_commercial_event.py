from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.core.models import Organization, UserProfile
from apps.leads.models import Lead, LeadProfile
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdLeadAttribution, AdvertisingSettings
from apps.advertising.providers.base import ProviderResult


class LeadCommercialEventViewTests(APITestCase):
    """
    Antes desta view, nada no sistema definia LeadProfile.is_reserved/is_purchased
    — sem isso, o loop de conversão (RESERVED/SOLD de volta pro Google Ads) nunca
    disparava. Esta é a única porta de entrada para esses dois estados.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Canil P')
        self.user = User.objects.create_user(username='userp', password='x')
        UserProfile.objects.create(user=self.user, organization=self.org)
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='4443332221')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp P', daily_budget=10,
            external_campaign_id='ext-1',
        )
        self.lead = Lead.objects.create(organization=self.org, phone='554891119999')
        self.client.force_authenticate(user=self.user)

    def _url(self, lead_id=None):
        return f'/api/leads/{lead_id or self.lead.id}/ad-commercial-event/'

    def test_invalid_event_type_rejected(self):
        resp = self.client.post(self._url(), {'event_type': 'bogus'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_lead_from_other_org_not_found(self):
        other_org = Organization.objects.create(name='Canil Q')
        other_lead = Lead.objects.create(organization=other_org, phone='554891110000')
        resp = self.client.post(self._url(other_lead.id), {'event_type': 'reservation'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_marks_reservation_and_creates_profile_if_missing(self):
        resp = self.client.post(self._url(), {'event_type': 'reservation'}, format='json')
        self.assertEqual(resp.status_code, 200)
        profile = LeadProfile.objects.get(lead=self.lead)
        self.assertTrue(profile.is_reserved)
        self.assertFalse(profile.is_purchased)

    def test_marks_sale_sets_both_flags(self):
        resp = self.client.post(self._url(), {'event_type': 'sale', 'value': 4500}, format='json')
        self.assertEqual(resp.status_code, 200)
        profile = LeadProfile.objects.get(lead=self.lead)
        self.assertTrue(profile.is_reserved)
        self.assertTrue(profile.is_purchased)

    def test_invalid_value_rejected(self):
        resp = self.client.post(self._url(), {'event_type': 'sale', 'value': 'não é número'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_repeating_event_does_not_fire_conversion_twice(self):
        AdLeadAttribution.objects.create(lead=self.lead, campaign=self.campaign, gclid='g1')
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=True)

        with patch('apps.advertising.services.conversion_service.ConversionService.record_event') as mock_record:
            self.client.post(self._url(), {'event_type': 'reservation'}, format='json')
            resp2 = self.client.post(self._url(), {'event_type': 'reservation'}, format='json')

        mock_record.assert_called_once()
        self.assertEqual(resp2.data['status'], 'already_recorded')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.upload_conversion')
    def test_sale_triggers_real_conversion_upload_with_value_when_attributed(self, mock_upload):
        mock_upload.return_value = ProviderResult(success=True, raw={'ok': True})
        AdLeadAttribution.objects.create(lead=self.lead, campaign=self.campaign, gclid='g1')
        AdvertisingSettings.objects.create(organization=self.org, is_enabled=True)

        self.client.post(self._url(), {'event_type': 'sale', 'value': 4500}, format='json')

        mock_upload.assert_called_once()
        spec = mock_upload.call_args[0][1]
        self.assertEqual(spec.conversion_value, 4500.0)
        self.assertEqual(spec.gclid, 'g1')
