from datetime import date, timedelta

from django.test import TestCase

from apps.core.models import Organization
from apps.leads.models import Lead, LeadProfile
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdMetric, AdLeadAttribution
from apps.advertising.services.metrics_service import MetricsService


class BuildSnapshotTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil N')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9998887776')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp N',
            daily_budget=10, external_campaign_id='ext-9',
        )

    def test_snapshot_never_fabricates_ratios_without_data(self):
        snapshot = MetricsService().build_snapshot(self.campaign)
        self.assertEqual(snapshot['cost'], 0)
        self.assertEqual(snapshot['impressions'], 0)
        self.assertEqual(snapshot['clicks'], 0)
        self.assertIsNone(snapshot['ctr'])
        self.assertIsNone(snapshot['average_cpc'])
        self.assertIsNone(snapshot['cost_per_lead'])
        self.assertIsNone(snapshot['cac'])

    def test_snapshot_aggregates_real_stored_metrics_and_funnel(self):
        AdMetric.objects.create(
            campaign=self.campaign, date=date.today() - timedelta(days=1),
            impressions=1000, clicks=50, cost=200, conversions=3,
        )
        AdMetric.objects.create(
            campaign=self.campaign, date=date.today() - timedelta(days=2),
            impressions=500, clicks=25, cost=100, conversions=1,
        )

        lead_qualified = Lead.objects.create(
            organization=self.org, phone='554891112222', status='QUALIFYING', lead_classification='HOT_LEAD',
        )
        AdLeadAttribution.objects.create(lead=lead_qualified, campaign=self.campaign, gclid='g1')

        lead_sold = Lead.objects.create(organization=self.org, phone='554891113333', status='HANDOFF')
        LeadProfile.objects.create(lead=lead_sold, is_reserved=True, is_purchased=True)
        AdLeadAttribution.objects.create(lead=lead_sold, campaign=self.campaign, gclid='g2')

        snapshot = MetricsService().build_snapshot(self.campaign)

        self.assertEqual(snapshot['cost'], 300.0)
        self.assertEqual(snapshot['impressions'], 1500)
        self.assertEqual(snapshot['clicks'], 75)
        self.assertEqual(snapshot['conversions'], 4)
        self.assertEqual(snapshot['total_leads'], 2)
        self.assertEqual(snapshot['qualified_leads'], 2)
        self.assertEqual(snapshot['sales'], 1)
        self.assertEqual(snapshot['reservations'], 1)
        self.assertEqual(snapshot['cac'], 300.0)
        self.assertEqual(snapshot['ctr'], round(75 / 1500, 2))

    def test_snapshot_ignores_metrics_outside_window(self):
        AdMetric.objects.create(
            campaign=self.campaign, date=date.today() - timedelta(days=60),
            impressions=999, clicks=99, cost=999, conversions=9,
        )
        snapshot = MetricsService().build_snapshot(self.campaign, days_back=30)
        self.assertEqual(snapshot['cost'], 0)
        self.assertEqual(snapshot['impressions'], 0)
