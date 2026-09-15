import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.core.models import Organization
from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdChatMessage, AdvertisingSettings,
    AdCampaignBriefing, AdAgentDecision,
)
from apps.advertising.services.agent_service import AdvertisingAgentService
from apps.advertising.services.skill_service import load_skill, format_briefing


def _mock_message(content=None, tool_calls=None):
    return MagicMock(content=content, tool_calls=tool_calls)


def _mock_tool_call(call_id, name, arguments):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    tc.model_dump.return_value = {'id': call_id, 'function': {'name': name, 'arguments': json.dumps(arguments)}}
    return tc


class SkillServiceTests(TestCase):
    def test_skill_file_loads_and_is_not_empty(self):
        text = load_skill()
        self.assertIn('CLIQUE NÃO É O OBJETIVO', text)

    def test_format_briefing_without_briefing(self):
        self.assertIn('Nenhum briefing', format_briefing(None))

    def test_format_briefing_with_data(self):
        org = Organization.objects.create(name='Canil Briefing')
        account = AdvertisingAccount.objects.create(organization=org, customer_id='1112223335')
        campaign = AdCampaign.objects.create(organization=org, advertising_account=account, name='C', daily_budget=10)
        briefing = AdCampaignBriefing.objects.create(
            campaign=campaign, product_description='Filhotes Border Collie',
            priority_regions={'A': ['Florianópolis', 'Itajaí']},
            do_not_negate_keywords=['preço', 'criador'],
        )
        text = format_briefing(briefing)
        self.assertIn('Filhotes Border Collie', text)
        self.assertIn('Florianópolis', text)
        self.assertIn('NUNCA negativar', text)


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
    def test_pause_tool_call_goes_through_campaign_service_and_logs_decision(self, mock_openai_cls, mock_pause):
        paused_campaign = AdCampaign.objects.get(id=self.campaign.id)
        paused_campaign.status = 'paused'
        mock_pause.return_value = paused_campaign

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'pause_campaign', {'reason': 'CPL disparou'})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Pausei a campanha para você.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Pausa a campanha', openai_api_key='sk-test')

        mock_pause.assert_called_once_with(self.org, self.campaign.id, reason='CPL disparou', performed_by='agent')
        self.assertEqual(reply.content, 'Pausei a campanha para você.')
        self.assertEqual(reply.actions_taken[0]['tool'], 'pause_campaign')

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_small_budget_change_auto_executes(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # 20 -> 22 é 10%, dentro do limite padrão de 20%
        tool_call = _mock_tool_call('call_1', 'update_daily_budget', {'daily_budget': 22})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Orçamento atualizado.')),
        ]

        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider.update_campaign') as mock_update:
            mock_update.return_value = None
            AdvertisingAgentService(self.campaign).chat(user_message='Aumenta pra 22', openai_api_key='sk-test')

        self.campaign.refresh_from_db()
        self.assertEqual(float(self.campaign.daily_budget), 22)
        self.assertTrue(AdAgentDecision.objects.filter(campaign=self.campaign, action='update_daily_budget').exists())

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_large_budget_change_requires_approval_and_does_not_execute(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # 20 -> 50 é 150%, muito acima do limite padrão de 20%
        tool_call = _mock_tool_call('call_1', 'update_daily_budget', {'daily_budget': 50})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Isso é um aumento grande, você confirma?')),
        ]

        with patch('apps.advertising.services.campaign_service.CampaignService.update_daily_budget') as mock_update_budget:
            AdvertisingAgentService(self.campaign).chat(user_message='Aumenta pra 50', openai_api_key='sk-test')
            mock_update_budget.assert_not_called()

        self.campaign.refresh_from_db()
        self.assertEqual(float(self.campaign.daily_budget), 20)  # não mudou

    @patch('apps.advertising.services.campaign_service.CampaignService.update_daily_budget')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_confirmed_large_budget_change_executes(self, mock_openai_cls, mock_update_budget):
        updated = AdCampaign.objects.get(id=self.campaign.id)
        updated.daily_budget = 50
        mock_update_budget.return_value = updated

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'update_daily_budget', {'daily_budget': 50, 'confirmed': True})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Feito, orçamento em R$ 50.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Confirmo, pode mudar pra 50', openai_api_key='sk-test')

        mock_update_budget.assert_called_once()

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_respects_org_specific_auto_approval_threshold(self, mock_openai_cls):
        AdvertisingSettings.objects.create(organization=self.org, max_auto_budget_change_percent=200)

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'update_daily_budget', {'daily_budget': 50})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Orçamento atualizado.')),
        ]

        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider.update_campaign'):
            AdvertisingAgentService(self.campaign).chat(user_message='Aumenta pra 50', openai_api_key='sk-test')

        self.campaign.refresh_from_db()
        self.assertEqual(float(self.campaign.daily_budget), 50)  # limite de 200% liberou

    @patch('apps.advertising.services.campaign_service.CampaignService.add_negative_keywords')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_negative_keywords_blocked_by_briefing_are_filtered_out(self, mock_openai_cls, mock_add_negatives):
        AdCampaignBriefing.objects.create(campaign=self.campaign, do_not_negate_keywords=['preço', 'criador'])
        mock_add_negatives.return_value = self.campaign

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'add_negative_keywords', {'keywords': ['grátis', 'preço', 'adoção']})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Adicionei as negativas seguras.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Negativa grátis, preço e adoção', openai_api_key='sk-test')

        mock_add_negatives.assert_called_once()
        call_args = mock_add_negatives.call_args
        self.assertEqual(set(call_args[0][2]), {'grátis', 'adoção'})  # 'preço' filtrado
        self.assertIn('blocked_by_briefing', reply.actions_taken[0]['result'])

    @patch('apps.advertising.services.campaign_service.CampaignService.get_search_terms')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_get_search_terms_tool(self, mock_openai_cls, mock_get_terms):
        mock_get_terms.return_value = [{'search_term': 'border collie grátis', 'cost': 12.5, 'conversions': 0}]

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'get_search_terms', {'days_back': 14})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Achei um termo desperdiçando dinheiro.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Tem termo desperdiçando dinheiro?', openai_api_key='sk-test')

        mock_get_terms.assert_called_once_with(self.campaign, 14)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_get_lead_funnel_tool_returns_real_counts(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'get_lead_funnel', {})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Ainda não há leads suficientes.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Como está o funil?', openai_api_key='sk-test')
        self.assertEqual(reply.content, 'Ainda não há leads suficientes.')

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_get_decision_history_tool(self, mock_openai_cls):
        AdAgentDecision.objects.create(
            organization=self.org, campaign=self.campaign, action='pause_campaign',
            before={'status': 'active'}, after={'status': 'paused'}, reason='teste',
        )
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'get_decision_history', {'limit': 5})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Você já pausou essa campanha antes.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Já mexemos nisso antes?', openai_api_key='sk-test')
        self.assertEqual(reply.content, 'Você já pausou essa campanha antes.')

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_chat_history_is_persisted_in_order(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(_mock_message(content='ok'))

        AdvertisingAgentService(self.campaign).chat(user_message='oi', openai_api_key='sk-test')

        messages = list(AdChatMessage.objects.filter(campaign=self.campaign).order_by('created_at'))
        self.assertEqual([m.role for m in messages], ['user', 'assistant'])
        self.assertEqual(messages[0].content, 'oi')
