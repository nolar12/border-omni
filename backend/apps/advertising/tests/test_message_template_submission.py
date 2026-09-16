"""
MessageTemplateViewSet._submit_to_meta (api/views/__init__.py) é usado pela criação do
template de notificação de revisão de anúncios (ver notify_service.py) — a Meta rejeita
(INVALID_FORMAT) um template com variáveis {{n}} no corpo sem um example.body_text. Este
teste vive em apps/advertising porque foi esta feature que expôs o bug, embora o código
corrigido seja de api/views (que não é um app Django registrado, sem convenção de teste
própria).
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.core.models import Organization
from apps.channels.models import ChannelProvider
from apps.conversations.models import MessageTemplate
from api.views import MessageTemplateViewSet


class SubmitToMetaExampleBodyTextTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil Template')
        self.channel = ChannelProvider.objects.create(
            organization=self.org, provider='whatsapp', is_active=True,
            business_account_id='waba-1', access_token='tok',
        )

    @patch('requests.post')
    def test_body_with_variables_includes_example_in_order(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'id': 'meta-1'})
        template = MessageTemplate.objects.create(
            organization=self.org, name='t1', language='pt_BR', channel=self.channel,
            body_text='Olá {{1}}, sua campanha {{2}} tem novidade.',
        )

        MessageTemplateViewSet()._submit_to_meta(template)

        body_component = next(c for c in mock_post.call_args.kwargs['json']['components'] if c['type'] == 'BODY')
        self.assertEqual(body_component['example']['body_text'], [['Exemplo1', 'Exemplo2']])

    @patch('requests.post')
    def test_body_without_variables_has_no_example(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'id': 'meta-2'})
        template = MessageTemplate.objects.create(
            organization=self.org, name='t2', language='pt_BR', channel=self.channel,
            body_text='Mensagem fixa, sem variáveis.',
        )

        MessageTemplateViewSet()._submit_to_meta(template)

        body_component = next(c for c in mock_post.call_args.kwargs['json']['components'] if c['type'] == 'BODY')
        self.assertNotIn('example', body_component)
