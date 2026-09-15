from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.kennel.models import Litter
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdCampaignPlan, AdAgentDecision
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.providers.base import ProviderCampaign
from apps.advertising.services.campaign_plan_service import CampaignPlanService


class CampaignPlanServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil Plan')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1112223330')
        self.litter = Litter.objects.create(organization=self.org, name='Ninhada Setembro')

    def test_propose_never_creates_a_real_campaign(self):
        plan = CampaignPlanService().propose(
            organization=self.org, litter=self.litter,
            data={'daily_budget': 30, 'region': 'Florianópolis, Itajaí'},
            justification='Público qualificado nessas cidades.',
        )
        self.assertEqual(plan.status, 'proposed')
        self.assertEqual(AdCampaign.objects.count(), 0)
        self.assertTrue(plan.headlines)  # gerado via ai_copy_service (fallback de template)
        self.assertTrue(plan.descriptions)

    def test_propose_without_litter_does_not_touch_ad_copy_generation(self):
        plan = CampaignPlanService().propose(
            organization=self.org, litter=None,
            data={'daily_budget': 15, 'name': 'Campanha Geral', 'headlines': ['Ótimos Filhotes'], 'descriptions': ['Fale conosco.']},
        )
        self.assertIsNone(plan.litter)
        self.assertEqual(plan.headlines, ['Ótimos Filhotes'])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_execute_creates_campaign_via_existing_campaign_service_and_logs_decision(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-plan-1', status='active')
        plan = CampaignPlanService().propose(
            organization=self.org, litter=self.litter, data={'daily_budget': 25, 'region': 'Itajaí'},
        )

        campaign = CampaignPlanService().execute(organization=self.org, plan_id=plan.id)

        plan.refresh_from_db()
        self.assertEqual(plan.status, 'executed')
        self.assertEqual(plan.resulting_campaign_id, campaign.id)
        self.assertEqual(campaign.litter_id, self.litter.id)
        self.assertTrue(
            AdAgentDecision.objects.filter(campaign=campaign, action='execute_campaign_plan').exists()
        )

    def test_execute_without_account_raises_friendly_error(self):
        self.account.delete()
        plan = CampaignPlanService().propose(organization=self.org, litter=None, data={'daily_budget': 10})
        with self.assertRaises(GoogleAdsProviderError):
            CampaignPlanService().execute(organization=self.org, plan_id=plan.id)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_execute_is_idempotent_for_the_same_plan(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-plan-2', status='active')
        plan = CampaignPlanService().propose(organization=self.org, litter=None, data={'daily_budget': 10})

        first = CampaignPlanService().execute(organization=self.org, plan_id=plan.id)
        second = CampaignPlanService().execute(organization=self.org, plan_id=plan.id)

        self.assertEqual(first.id, second.id)
        mock_create.assert_called_once()

    def test_reject_marks_plan_and_blocks_execution(self):
        plan = CampaignPlanService().propose(organization=self.org, litter=None, data={'daily_budget': 10})
        rejected = CampaignPlanService().reject(organization=self.org, plan_id=plan.id)
        self.assertEqual(rejected.status, 'rejected')

        with self.assertRaises(GoogleAdsProviderError):
            CampaignPlanService().execute(organization=self.org, plan_id=plan.id)
