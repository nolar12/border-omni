import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.core.models import Organization, UserProfile
from apps.kennel.models import Litter
from apps.advertising.services.ai_copy_service import generate_ad_copy_with_fallback


class AiCopyServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil H')
        self.litter = Litter.objects.create(organization=self.org, name='Ninhada X')

    def test_falls_back_to_template_without_audience_description(self):
        result = generate_ad_copy_with_fallback(
            litter=self.litter, user_profile=None, audience_description='', openai_api_key='sk-test',
        )
        self.assertTrue(result['ad_headlines'])
        self.assertTrue(result['ad_descriptions'])

    def test_falls_back_to_template_without_api_key(self):
        result = generate_ad_copy_with_fallback(
            litter=self.litter, user_profile=None, audience_description='alto poder aquisitivo', openai_api_key='',
        )
        self.assertTrue(result['ad_headlines'])

    @patch('apps.advertising.services.ai_copy_service.OpenAI')
    def test_uses_ai_response_when_available(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                'headlines': ['Filhotes Premium BC', 'Linhagem Campeã', 'Exclusividade Garantida'],
                'descriptions': ['Filhotes de linhagem premiada, para famílias exigentes.', 'Atendimento exclusivo e acompanhamento vitalício.'],
                'keywords': ['border collie premium', 'filhote linhagem campea'],
            })))]
        )
        result = generate_ad_copy_with_fallback(
            litter=self.litter, user_profile=None,
            audience_description='famílias de alto poder aquisitivo', openai_api_key='sk-test',
        )
        self.assertIn('Filhotes Premium BC', result['ad_headlines'])
        self.assertEqual(len(result['ad_keywords']), 2)

    @patch('apps.advertising.services.ai_copy_service.OpenAI')
    def test_falls_back_to_template_when_ai_raises(self, mock_openai_cls):
        mock_openai_cls.side_effect = Exception('API indisponível')
        result = generate_ad_copy_with_fallback(
            litter=self.litter, user_profile=None,
            audience_description='alto poder aquisitivo', openai_api_key='sk-test',
        )
        self.assertTrue(result['ad_headlines'])
