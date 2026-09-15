import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdChatMessage
from apps.advertising.services.agent_service import AdvertisingAgentService


def _mock_message(content=None, tool_calls=None):
    return MagicMock(content=content, tool_calls=tool_calls)


def _mock_tool_call(call_id, name, arguments):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    tc.model_dump.return_value = {'id': call_id, 'function': {'name': name, 'arguments': json.dumps(arguments)}}
    return tc


class AdvertisingAgentServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil J')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9998887771')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp J',
            daily_budget=20, status='active', external_campaign_id='ext-1',
        )

    def _completion_with(self, message):
        return MagicMock(choices=[MagicMock(message=message)])

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_plain_reply_is_persisted_without_tool_calls(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(
            _mock_message(content='A campanha está ativa e saudável.')
        )

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Como está a campanha?', openai_api_key='sk-test')

        self.assertEqual(reply.role, 'assistant')
        self.assertEqual(reply.content, 'A campanha está ativa e saudável.')
        self.assertEqual(AdChatMessage.objects.filter(campaign=self.campaign).count(), 2)  # user + assistant

    @patch('apps.advertising.services.campaign_service.CampaignService.pause_campaign')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_pause_tool_call_goes_through_campaign_service(self, mock_openai_cls, mock_pause):
        paused_campaign = AdCampaign.objects.get(id=self.campaign.id)
        paused_campaign.status = 'paused'
        mock_pause.return_value = paused_campaign

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'pause_campaign', {})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Pausei a campanha para você.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Pausa a campanha', openai_api_key='sk-test')

        mock_pause.assert_called_once_with(self.org, self.campaign.id)
        self.assertEqual(reply.content, 'Pausei a campanha para você.')
        self.assertEqual(reply.actions_taken[0]['tool'], 'pause_campaign')

    @patch('apps.advertising.services.campaign_service.CampaignService.update_daily_budget')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_budget_tool_call_passes_argument_through(self, mock_openai_cls, mock_update_budget):
        updated_campaign = AdCampaign.objects.get(id=self.campaign.id)
        updated_campaign.daily_budget = 50
        mock_update_budget.return_value = updated_campaign

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'update_daily_budget', {'daily_budget': 50})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Orçamento atualizado para R$ 50.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Aumenta o orçamento pra 50', openai_api_key='sk-test')

        mock_update_budget.assert_called_once_with(self.org, self.campaign.id, 50)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_chat_history_is_persisted_in_order(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(_mock_message(content='ok'))

        AdvertisingAgentService(self.campaign).chat(user_message='oi', openai_api_key='sk-test')

        messages = list(AdChatMessage.objects.filter(campaign=self.campaign).order_by('created_at'))
        self.assertEqual([m.role for m in messages], ['user', 'assistant'])
        self.assertEqual(messages[0].content, 'oi')
