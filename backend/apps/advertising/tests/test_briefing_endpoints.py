from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.core.models import Organization, UserProfile
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdCampaignBriefing, AdAgentDecision


class BriefingEndpointTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil O')
        self.user = User.objects.create_user(username='usero', password='x')
        UserProfile.objects.create(user=self.user, organization=self.org)
        account = AdvertisingAccount.objects.create(organization=self.org, customer_id='4445556661')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=account, name='Camp O', daily_budget=10,
        )
        self.client.force_authenticate(user=self.user)

    def test_get_briefing_creates_empty_one_if_missing(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/briefing/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AdCampaignBriefing.objects.filter(campaign=self.campaign).exists())

    def test_put_briefing_updates_fields(self):
        resp = self.client.put(f'/api/ad-campaigns/{self.campaign.id}/briefing/', {
            'product_description': 'Filhotes X',
            'priority_regions': {'A': ['Cidade1']},
            'do_not_negate_keywords': ['preço'],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        briefing = AdCampaignBriefing.objects.get(campaign=self.campaign)
        self.assertEqual(briefing.product_description, 'Filhotes X')
        self.assertEqual(briefing.priority_regions, {'A': ['Cidade1']})

    def test_decisions_endpoint_lists_history(self):
        AdAgentDecision.objects.create(
            organization=self.org, campaign=self.campaign, action='pause_campaign',
            before={'status': 'active'}, after={'status': 'paused'},
        )
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/decisions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['action'], 'pause_campaign')

    def test_funnel_endpoint_returns_summary_shape(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/funnel/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('stages', resp.data)
        self.assertIn('total_leads', resp.data)

    def test_dashboard_endpoint_returns_snapshot_and_breakdowns(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('snapshot', resp.data)
        self.assertIn('city_breakdown', resp.data)
        self.assertIn('keyword_breakdown', resp.data)
        for key in ('cost', 'qualified_leads', 'cost_per_qualified_lead', 'negotiations', 'reservations', 'sales', 'cac'):
            self.assertIn(key, resp.data['snapshot'])

    def test_dashboard_endpoint_respects_days_back(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/dashboard/?days_back=7')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['snapshot']['period_days'], 7)

    def test_dashboard_endpoint_rejects_invalid_days_back(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/dashboard/?days_back=abc')
        self.assertEqual(resp.status_code, 400)
