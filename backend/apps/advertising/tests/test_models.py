from django.test import TestCase

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdMetric


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Canil A')
        self.org_b = Organization.objects.create(name='Canil B')
        self.account_a = AdvertisingAccount.objects.create(
            organization=self.org_a, customer_id='1112223333',
        )
        self.account_b = AdvertisingAccount.objects.create(
            organization=self.org_b, customer_id='4445556666',
        )

    def test_campaigns_are_scoped_by_organization(self):
        AdCampaign.objects.create(
            organization=self.org_a, advertising_account=self.account_a,
            name='Campanha A', daily_budget=20,
        )
        AdCampaign.objects.create(
            organization=self.org_b, advertising_account=self.account_b,
            name='Campanha B', daily_budget=30,
        )
        self.assertEqual(AdCampaign.objects.filter(organization=self.org_a).count(), 1)
        self.assertEqual(AdCampaign.objects.filter(organization=self.org_b).count(), 1)
        self.assertEqual(
            AdCampaign.objects.filter(organization=self.org_a).first().name, 'Campanha A'
        )

    def test_unique_account_per_org_provider_customer(self):
        with self.assertRaises(Exception):
            AdvertisingAccount.objects.create(
                organization=self.org_a, provider='google_ads', customer_id='1112223333',
            )

    def test_metric_unique_per_campaign_and_date(self):
        campaign = AdCampaign.objects.create(
            organization=self.org_a, advertising_account=self.account_a,
            name='Campanha A', daily_budget=20,
        )
        AdMetric.objects.create(campaign=campaign, date='2026-08-01', clicks=5)
        with self.assertRaises(Exception):
            AdMetric.objects.create(campaign=campaign, date='2026-08-01', clicks=9)


class RefreshTokenEncryptionTests(TestCase):
    def test_refresh_token_roundtrips(self):
        org = Organization.objects.create(name='Canil C')
        account = AdvertisingAccount.objects.create(
            organization=org, customer_id='9998887777', refresh_token='1//fake-refresh-token',
        )
        account.refresh_from_db()
        self.assertEqual(account.refresh_token, '1//fake-refresh-token')
