from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.core.models import Organization, UserProfile, AgentConfig
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdChatMessage


class ChatEndpointTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil K')
        self.user = User.objects.create_user(username='userk', password='x')
        UserProfile.objects.create(user=self.user, organization=self.org)
        AgentConfig.objects.create(organization=self.org, openai_api_key='sk-test')
        account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1234567890')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=account, name='Camp K', daily_budget=10,
        )
        self.client.force_authenticate(user=self.user)

    def test_chat_requires_message(self):
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.advertising.views.AdvertisingAgentService.chat')
    def test_chat_returns_agent_reply(self, mock_chat):
        mock_chat.return_value = AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant', content='Oi!',
        )
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/', {'message': 'Olá'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['content'], 'Oi!')

    def test_chat_without_openai_key_returns_503(self):
        self.org.agent_config.openai_api_key = ''
        self.org.agent_config.save()
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/', {'message': 'Olá'}, format='json')
        self.assertEqual(resp.status_code, 503)

    def test_chat_history_get(self):
        AdChatMessage.objects.create(organization=self.org, campaign=self.campaign, role='user', content='oi')
        resp = self.client.get(f'/api/ad-campaigns/{self.campaign.id}/chat/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    @patch('apps.advertising.views.transcribe_audio_file')
    def test_transcribe_returns_text(self, mock_transcribe):
        mock_transcribe.return_value = 'aumenta o orçamento pra cinquenta reais'
        audio = SimpleUploadedFile('audio.webm', b'fake-audio-bytes', content_type='audio/webm')
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/transcribe/', {'audio': audio}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['transcription'], 'aumenta o orçamento pra cinquenta reais')

    def test_transcribe_requires_audio_file(self):
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/transcribe/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.advertising.views.MetricsService.sync_campaign_metrics')
    @patch('apps.advertising.views.AdvertisingAgentService.run_proactive_review')
    def test_proactive_review_endpoint_returns_message_when_relevant(self, mock_review, mock_sync):
        mock_review.return_value = AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant',
            content='Itajaí está indo bem.', is_proactive=True,
        )
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/proactive-review/')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['is_proactive'])
        mock_sync.assert_called_once()

    @patch('apps.advertising.views.MetricsService.sync_campaign_metrics')
    @patch('apps.advertising.views.AdvertisingAgentService.run_proactive_review')
    def test_proactive_review_endpoint_returns_nothing_to_report(self, mock_review, mock_sync):
        mock_review.return_value = None
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/proactive-review/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'nothing_to_report')

    def test_proactive_review_without_openai_key_returns_503(self):
        self.org.agent_config.openai_api_key = ''
        self.org.agent_config.save()
        resp = self.client.post(f'/api/ad-campaigns/{self.campaign.id}/chat/proactive-review/')
        self.assertEqual(resp.status_code, 503)
