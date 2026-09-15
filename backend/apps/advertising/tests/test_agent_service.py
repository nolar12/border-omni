import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.kennel.models import Litter
from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdChatMessage, AdvertisingSettings,
    AdCampaignBriefing, AdAgentDecision, AdCampaignPlan,
)
from apps.advertising.providers.base import ProviderCampaign
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
    def test_evaluate_decision_without_stored_snapshot_refuses_to_invent_numbers(self, mock_openai_cls):
        decision = AdAgentDecision.objects.create(
            organization=self.org, campaign=self.campaign, action='pause_campaign',
            before={'status': 'active'}, after={'status': 'paused'}, reason='teste antigo',
        )
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'evaluate_decision', {'decision_id': decision.id})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Não tenho dado histórico suficiente para essa decisão.')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Como foi aquela pausa?', openai_api_key='sk-test')

        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertFalse(tool_result['has_before_snapshot'])
        self.assertEqual(reply.content, 'Não tenho dado histórico suficiente para essa decisão.')

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_evaluate_decision_with_stored_snapshot_computes_real_delta(self, mock_openai_cls):
        decision = AdAgentDecision.objects.create(
            organization=self.org, campaign=self.campaign, action='update_daily_budget',
            before={'daily_budget': '20'}, after={'daily_budget': '30'}, reason='teste',
            metrics_snapshot={
                'cost': 100.0, 'impressions': 1000, 'clicks': 50, 'ctr': 0.05, 'average_cpc': 2.0,
                'conversions': 2, 'conversion_rate': 0.04, 'total_leads': 2, 'cost_per_lead': 50.0,
                'qualified_leads': 1, 'cost_per_qualified_lead': 100.0, 'negotiations': 0,
                'reservations': 0, 'sales': 0, 'cac': None,
            },
        )

        from apps.leads.models import Lead
        from apps.advertising.models import AdMetric, AdLeadAttribution
        AdMetric.objects.create(campaign=self.campaign, date='2026-09-01', impressions=2000, clicks=120, cost=250, conversions=5)
        lead = Lead.objects.create(organization=self.org, phone='554891114444', status='QUALIFYING', lead_classification='HOT_LEAD')
        AdLeadAttribution.objects.create(lead=lead, campaign=self.campaign, gclid='g1')

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'evaluate_decision', {'decision_id': decision.id})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='O custo por lead qualificado melhorou depois da mudança.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Como foi aquele aumento de orçamento?', openai_api_key='sk-test')

        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertTrue(tool_result['has_before_snapshot'])
        self.assertEqual(tool_result['metrics_now']['cost'], 250.0)
        self.assertEqual(tool_result['delta']['cost'], 150.0)
        self.assertEqual(tool_result['delta']['impressions'], 1000)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_propose_campaign_plan_never_creates_a_real_campaign(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'propose_campaign_plan', {'daily_budget': 30, 'region': 'Itajaí'})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Aqui está a proposta, posso executar?')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Crie uma campanha para esta ninhada', openai_api_key='sk-test')

        self.assertEqual(AdCampaignPlan.objects.count(), 1)
        self.assertEqual(AdCampaign.objects.count(), 1)  # só a campanha do setUp — nenhuma nova criada
        plan = AdCampaignPlan.objects.get()
        self.assertEqual(plan.status, 'proposed')

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_execute_campaign_plan_without_confirmation_does_not_execute(self, mock_openai_cls):
        plan = AdCampaignPlan.objects.create(organization=self.org, daily_budget=20, name='Plano X')

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'execute_campaign_plan', {'plan_id': plan.id})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Você confirma a criação?')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Pode criar', openai_api_key='sk-test')

        plan.refresh_from_db()
        self.assertEqual(plan.status, 'proposed')
        self.assertEqual(AdCampaign.objects.count(), 1)  # só a do setUp

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_execute_campaign_plan_with_confirmation_creates_the_campaign(self, mock_openai_cls, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-plan-x', status='active')
        plan = AdCampaignPlan.objects.create(organization=self.org, daily_budget=20, name='Plano Y')

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'execute_campaign_plan', {'plan_id': plan.id, 'confirmed': True})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Campanha criada com sucesso.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Confirmo, pode criar', openai_api_key='sk-test')

        plan.refresh_from_db()
        self.assertEqual(plan.status, 'executed')
        self.assertEqual(AdCampaign.objects.filter(name='Plano Y').count(), 1)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_propose_campaign_plan_defaults_to_current_campaign_litter(self, mock_openai_cls):
        litter = Litter.objects.create(organization=self.org, name='Ninhada Atual')
        self.campaign.litter = litter
        self.campaign.save(update_fields=['litter'])

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'propose_campaign_plan', {'daily_budget': 20})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Proposta pronta.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Crie uma campanha para esta ninhada', openai_api_key='sk-test')

        plan = AdCampaignPlan.objects.get()
        self.assertEqual(plan.litter_id, litter.id)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_get_city_breakdown_tool_returns_real_city_data(self, mock_openai_cls):
        from apps.leads.models import Lead
        from apps.advertising.models import AdLeadAttribution
        lead = Lead.objects.create(organization=self.org, phone='554891115555', city='Itajaí', status='QUALIFIED')
        AdLeadAttribution.objects.create(lead=lead, campaign=self.campaign, gclid='g1')

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'get_city_breakdown', {})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Itajaí está performando melhor.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Qual cidade está melhor?', openai_api_key='sk-test')

        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertEqual(tool_result['cities'][0]['group'], 'Itajaí')
        self.assertEqual(tool_result['cities'][0]['qualified_leads'], 1)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_get_keyword_breakdown_tool_never_confuses_keyword_with_search_term(self, mock_openai_cls):
        from apps.leads.models import Lead, LeadProfile
        from apps.advertising.models import AdLeadAttribution
        lead = Lead.objects.create(organization=self.org, phone='554891116666')
        LeadProfile.objects.create(lead=lead, is_reserved=True, is_purchased=True)
        AdLeadAttribution.objects.create(
            lead=lead, campaign=self.campaign, gclid='g1',
            keyword='border collie filhote', search_term='quanto custa um filhote de border collie',
        )

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'get_keyword_breakdown', {})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='A keyword "border collie filhote" trouxe uma venda.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Qual keyword trouxe compradores?', openai_api_key='sk-test')

        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertEqual(tool_result['keywords'][0]['group'], 'border collie filhote')
        self.assertEqual(tool_result['keywords'][0]['sales'], 1)

    @patch('apps.advertising.services.docs_research_service.requests.get')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_fetch_official_documentation_tool_is_read_only_and_not_logged_as_action(self, mock_openai_cls, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text='<p>Conteúdo oficial sobre ValueTrack.</p>')

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'fetch_official_documentation', {'url': 'https://support.google.com/google-ads/answer/6305348'})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='O ValueTrack funciona assim...')),
        ]

        reply = AdvertisingAgentService(self.campaign).chat(user_message='Como funciona ValueTrack hoje?', openai_api_key='sk-test')

        self.assertEqual(reply.actions_taken, [])  # ferramenta de leitura não conta como "ação"
        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertIn('ValueTrack', tool_result['content'])

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_fetch_official_documentation_rejects_disallowed_domain(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'fetch_official_documentation', {'url': 'https://example.com/scam'})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='Não posso consultar essa fonte.')),
        ]

        AdvertisingAgentService(self.campaign).chat(user_message='Veja em example.com', openai_api_key='sk-test')

        tool_result = json.loads(mock_client.chat.completions.create.call_args_list[1][1]['messages'][-1]['content'])
        self.assertIn('error', tool_result)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_chat_history_is_persisted_in_order(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(_mock_message(content='ok'))

        AdvertisingAgentService(self.campaign).chat(user_message='oi', openai_api_key='sk-test')

        messages = list(AdChatMessage.objects.filter(campaign=self.campaign).order_by('created_at'))
        self.assertEqual([m.role for m in messages], ['user', 'assistant'])
        self.assertEqual(messages[0].content, 'oi')


class ProactiveReviewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil Proativo')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9998887772')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp Proativa',
            daily_budget=20, status='active', external_campaign_id='ext-1',
        )

    def _completion_with(self, message):
        return MagicMock(choices=[MagicMock(message=message)])

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_sentinel_never_persists_a_chat_message(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(_mock_message(content='NADA_A_REPORTAR'))

        result = AdvertisingAgentService(self.campaign).run_proactive_review(openai_api_key='sk-test')

        self.assertIsNone(result)
        self.assertEqual(AdChatMessage.objects.filter(campaign=self.campaign).count(), 0)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_relevant_finding_is_persisted_as_proactive(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(
            _mock_message(content='Itajaí está trazendo os leads mais qualificados esta semana.')
        )

        result = AdvertisingAgentService(self.campaign).run_proactive_review(openai_api_key='sk-test')

        self.assertIsNotNone(result)
        self.assertTrue(result.is_proactive)
        self.assertEqual(result.role, 'assistant')
        # Não cria uma mensagem "user" correspondente — ninguém perguntou nada.
        self.assertEqual(AdChatMessage.objects.filter(campaign=self.campaign, role='user').count(), 0)

    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_mutating_tools_are_not_offered_during_proactive_review(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._completion_with(_mock_message(content='NADA_A_REPORTAR'))

        AdvertisingAgentService(self.campaign).run_proactive_review(openai_api_key='sk-test')

        offered_tools = mock_client.chat.completions.create.call_args[1]['tools']
        offered_names = {t['function']['name'] for t in offered_tools}
        self.assertNotIn('pause_campaign', offered_names)
        self.assertNotIn('update_daily_budget', offered_names)
        self.assertNotIn('execute_campaign_plan', offered_names)
        self.assertIn('get_lead_funnel', offered_names)

    @patch('apps.advertising.services.campaign_service.CampaignService.pause_campaign')
    @patch('apps.advertising.services.agent_service.OpenAI')
    def test_agent_cannot_actually_execute_a_mutation_even_if_it_tried(self, mock_openai_cls, mock_pause):
        """Defesa em profundidade: mesmo que o modelo tentasse chamar uma tool
        fora da lista oferecida, _execute_tool não reconheceria o nome."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tool_call = _mock_tool_call('call_1', 'pause_campaign', {'reason': 'tentativa indevida'})
        mock_client.chat.completions.create.side_effect = [
            self._completion_with(_mock_message(content=None, tool_calls=[tool_call])),
            self._completion_with(_mock_message(content='NADA_A_REPORTAR')),
        ]

        AdvertisingAgentService(self.campaign).run_proactive_review(openai_api_key='sk-test')

        mock_pause.assert_not_called()
