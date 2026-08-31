from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.core.models import Organization, UserProfile
from apps.kennel.models import Litter
from apps.advertising.models import AdvertisingAccount, AdCampaign


class CrossTenantPermissionTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Canil A')
        self.org_b = Organization.objects.create(name='Canil B')

        self.user_a = User.objects.create_user(username='usera', password='x')
        UserProfile.objects.create(user=self.user_a, organization=self.org_a)

        self.account_a = AdvertisingAccount.objects.create(organization=self.org_a, customer_id='1112223333')
        self.account_b = AdvertisingAccount.objects.create(organization=self.org_b, customer_id='4445556666')

        self.campaign_a = AdCampaign.objects.create(
            organization=self.org_a, advertising_account=self.account_a, name='Camp A', daily_budget=10,
        )
        self.campaign_b = AdCampaign.objects.create(
            organization=self.org_b, advertising_account=self.account_b, name='Camp B', daily_budget=10,
        )

        self.client.force_authenticate(user=self.user_a)

    def test_list_only_returns_own_org_campaigns(self):
        resp = self.client.get('/api/ad-campaigns/')
        self.assertEqual(resp.status_code, 200)
        names = [c['name'] for c in resp.data['results']] if isinstance(resp.data, dict) and 'results' in resp.data else [c['name'] for c in resp.data]
        self.assertIn('Camp A', names)
        self.assertNotIn('Camp B', names)

    def test_cannot_retrieve_other_org_campaign(self):
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_cannot_pause_other_org_campaign(self):
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign_b.id}/pause/')
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/ad-campaigns/')
        self.assertIn(resp.status_code, (401, 403))

    def test_cannot_promote_litter_belonging_to_other_org(self):
        litter_b = Litter.objects.create(organization=self.org_b, name='Ninhada B')
        resp = self.client.post('/api/ad-campaigns/promote-litter/', {
            'litter_id': litter_b.id, 'daily_budget': 10, 'client_request_id': 'req-x',
        }, format='json')
        self.assertEqual(resp.status_code, 404)


class PromoteLitterTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil G')
        self.user = User.objects.create_user(username='userg', password='x')
        UserProfile.objects.create(user=self.user, organization=self.org)
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9990001111')
        self.litter = Litter.objects.create(organization=self.org, name='Ninhada Agosto')
        self.client.force_authenticate(user=self.user)

    def test_promote_litter_without_account_returns_error(self):
        self.account.delete()
        resp = self.client.post('/api/ad-campaigns/promote-litter/', {
            'litter_id': self.litter.id, 'daily_budget': 15, 'client_request_id': 'req-1',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_promote_litter_creates_campaign_in_dry_run(self):
        resp = self.client.post('/api/ad-campaigns/promote-litter/', {
            'litter_id': self.litter.id, 'daily_budget': 15, 'region': 'Florianópolis/SC',
            'client_request_id': 'req-2',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AdCampaign.objects.get().litter_id, self.litter.id)
        self.assertTrue(len(resp.data['ad_headlines']) > 0)
