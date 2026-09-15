from unittest.mock import patch

from django.test import TestCase

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
