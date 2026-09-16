from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Organization, AgentConfig
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdvertisingSettings, AdChatMessage
from apps.advertising.tasks import run_proactive_campaign_reviews


class RunProactiveCampaignReviewsTaskTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil Task')
        AgentConfig.objects.create(organization=self.org, openai_api_key='sk-test')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1231231231')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp Task',
            daily_budget=10, status='active', external_campaign_id='ext-1',
        )

    @patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics')
    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_reviews_active_campaigns_with_openai_key(self, mock_review, mock_sync):
        mock_review.return_value = AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant', content='ok', is_proactive=True,
        )
        result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 1, 'posted': 1, 'errors': 0})
        mock_sync.assert_called_once()
        mock_review.assert_called_once()

    @patch('apps.advertising.services.notify_service.notify_admins_of_ad_review')
    @patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics')
    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_notifies_admins_by_whatsapp_when_review_is_posted(self, mock_review, mock_sync, mock_notify):
        message = AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant', content='ok', is_proactive=True,
        )
        mock_review.return_value = message
        run_proactive_campaign_reviews()
        mock_notify.assert_called_once_with(self.org, self.campaign, message)

    @patch('apps.advertising.services.notify_service.notify_admins_of_ad_review')
    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_does_not_notify_when_nothing_to_report(self, mock_review, mock_notify):
        mock_review.return_value = None
        with patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics'):
            run_proactive_campaign_reviews()
        mock_notify.assert_not_called()

    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_skips_campaigns_without_openai_key(self, mock_review):
        self.org.agent_config.openai_api_key = ''
        self.org.agent_config.save()
        result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 0, 'posted': 0, 'errors': 0})
        mock_review.assert_not_called()

    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_skips_org_with_proactive_review_disabled(self, mock_review):
        AdvertisingSettings.objects.create(organization=self.org, proactive_review_enabled=False)
        result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 0, 'posted': 0, 'errors': 0})
        mock_review.assert_not_called()

    @patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics')
    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_skips_non_active_campaigns(self, mock_review, mock_sync):
        self.campaign.status = 'paused'
        self.campaign.save(update_fields=['status'])
        result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 0, 'posted': 0, 'errors': 0})
        mock_review.assert_not_called()

    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_nothing_to_report_counts_as_reviewed_not_posted(self, mock_review):
        mock_review.return_value = None
        with patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics'):
            result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 1, 'posted': 0, 'errors': 0})

    @patch('apps.advertising.services.agent_service.AdvertisingAgentService.run_proactive_review')
    def test_error_in_one_campaign_does_not_stop_the_others(self, mock_review):
        other_account = AdvertisingAccount.objects.create(organization=self.org, customer_id='3213213210')
        AdCampaign.objects.create(
            organization=self.org, advertising_account=other_account, name='Camp Task 2',
            daily_budget=10, status='active', external_campaign_id='ext-2',
        )
        mock_review.side_effect = [RuntimeError('boom'), AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant', content='ok', is_proactive=True,
        )]
        with patch('apps.advertising.services.metrics_service.MetricsService.sync_campaign_metrics'):
            result = run_proactive_campaign_reviews()
        self.assertEqual(result, {'reviewed': 2, 'posted': 1, 'errors': 1})
