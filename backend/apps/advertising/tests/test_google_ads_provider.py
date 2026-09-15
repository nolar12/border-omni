from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount
from apps.advertising.providers.google_ads import GoogleAdsProvider


class SuggestGeoTargetConstantsTests(TestCase):
    """
    A API do Google retorna várias sugestões por termo buscado (a cidade, bairros,
    CEPs, cidades homônimas em outros estados) — o provider deve ficar só com a
    melhor (tipo "City") por termo, não segmentar tudo que veio na resposta.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Canil I')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1112223334')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_picks_only_the_city_match_per_search_term(self, mock_request):
        mock_request.return_value = {
            'geoTargetConstantSuggestions': [
                {'searchTerm': 'Camboriú', 'geoTargetConstant': {
                    'resourceName': 'geoTargetConstants/1031520', 'targetType': 'City',
                }},
                {'searchTerm': 'Camboriú', 'geoTargetConstant': {
                    'resourceName': 'geoTargetConstants/9197039', 'targetType': 'District',
                }},
                {'searchTerm': 'Camboriú', 'geoTargetConstant': {
                    'resourceName': 'geoTargetConstants/9102261', 'targetType': 'Postal Code',
                }},
            ],
        }
        result = GoogleAdsProvider().suggest_geo_target_constants(self.account, ['Camboriú'])
        self.assertEqual(result, ['geoTargetConstants/1031520'])

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_one_result_per_search_term(self, mock_request):
        mock_request.return_value = {
            'geoTargetConstantSuggestions': [
                {'searchTerm': 'Camboriú', 'geoTargetConstant': {'resourceName': 'geoTargetConstants/1', 'targetType': 'City'}},
                {'searchTerm': 'Itajaí', 'geoTargetConstant': {'resourceName': 'geoTargetConstants/2', 'targetType': 'City'}},
            ],
        }
        result = GoogleAdsProvider().suggest_geo_target_constants(self.account, ['Camboriú', 'Itajaí'])
        self.assertEqual(set(result), {'geoTargetConstants/1', 'geoTargetConstants/2'})

    def test_empty_locations_returns_empty_without_calling_api(self):
        result = GoogleAdsProvider().suggest_geo_target_constants(self.account, [])
        self.assertEqual(result, [])


class SearchTermsAndNegativesTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil N')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='3334445556')

    def test_get_search_terms_returns_empty_in_dry_run(self):
        result = GoogleAdsProvider().get_search_terms(self.account, 'ext-1')
        self.assertEqual(result, [])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_get_search_terms_parses_response(self, mock_request):
        mock_request.return_value = {
            'results': [{
                'searchTermView': {'searchTerm': 'border collie grátis'},
                'segments': {'keyword': {'info': {'text': 'border collie', 'matchType': 'BROAD'}}},
                'metrics': {'clicks': '3', 'costMicros': '12500000', 'conversions': '0', 'impressions': '50'},
            }],
        }
        result = GoogleAdsProvider().get_search_terms(self.account, 'ext-1')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['search_term'], 'border collie grátis')
        self.assertEqual(result[0]['cost'], 12.5)
        self.assertEqual(result[0]['conversions'], 0.0)

    def test_add_negative_keywords_noop_in_dry_run(self):
        # Não deve levantar exceção nem chamar a API real.
        GoogleAdsProvider().add_negative_keywords(self.account, 'customers/1/campaigns/1', ['grátis'])

    def test_add_negative_keywords_noop_with_empty_list(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().add_negative_keywords(self.account, 'customers/1/campaigns/1', [])
            mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_add_negative_keywords_sends_correct_payload(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().add_negative_keywords(self.account, 'customers/1/campaigns/1', ['grátis', 'adoção'])

        args, kwargs = mock_request.call_args
        operations = kwargs['json']['operations']
        self.assertEqual(len(operations), 2)
        self.assertTrue(all(op['create']['negative'] is True for op in operations))
        self.assertEqual({op['create']['keyword']['text'] for op in operations}, {'grátis', 'adoção'})
