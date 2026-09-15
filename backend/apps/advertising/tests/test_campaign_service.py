from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdAgentDecision
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.providers.base import ProviderCampaign
from apps.advertising.services.campaign_service import CampaignService


class CampaignServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil E')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1231231234')
        self.data = {'name': 'Ninhada Border Collie Agosto', 'daily_budget': 20}

    @override_settings(GOOGLE_ADS_ENABLED=False)
    def test_create_campaign_stays_draft_when_globally_disabled(self):
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'draft')
        self.assertIn('desabilitado', campaign.error_message)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_success_marks_active(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-123', status='active')
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'active')
        self.assertEqual(campaign.external_campaign_id, 'dryrun-123')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_provider_error_is_captured_never_raised(self, mock_create):
        mock_create.side_effect = GoogleAdsProviderError('Conta suspensa pelo Google.', code='account_suspended')
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'error')
        self.assertEqual(campaign.error_message, 'Conta suspensa pelo Google.')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_is_idempotent_via_client_request_id(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-abc', status='active')
        service = CampaignService()
        first = service.create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data=self.data, client_request_id='req-1',
        )
        second = service.create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data=self.data, client_request_id='req-1',
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(AdCampaign.objects.filter(client_request_id='req-1').count(), 1)
        mock_create.assert_called_once()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.resume_campaign')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.pause_campaign')
    def test_pause_and_resume_campaign(self, mock_pause, mock_resume):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X',
            daily_budget=10, status='active', external_campaign_id='ext-1',
        )
        service = CampaignService()

        paused = service.pause_campaign(self.org, campaign.id)
        self.assertEqual(paused.status, 'paused')
        mock_pause.assert_called_once()

        resumed = service.resume_campaign(self.org, campaign.id)
        self.assertEqual(resumed.status, 'active')
        mock_resume.assert_called_once()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.pause_campaign')
    def test_pause_campaign_logs_decision_with_real_metrics_snapshot(self, mock_pause):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X',
            daily_budget=10, status='active', external_campaign_id='ext-1',
        )
        CampaignService().pause_campaign(self.org, campaign.id, reason='teste')

        decision = AdAgentDecision.objects.get(campaign=campaign, action='pause_campaign')
        self.assertTrue(decision.metrics_snapshot)
        self.assertIn('cost', decision.metrics_snapshot)
        self.assertIn('qualified_leads', decision.metrics_snapshot)
        self.assertEqual(decision.metrics_snapshot['campaign_id'], campaign.id)
