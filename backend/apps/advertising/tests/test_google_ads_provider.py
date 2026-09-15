from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount
from apps.advertising.providers.base import ConversionSpec
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


class ResumeCampaignTests(TestCase):
    """
    Toda campanha/grupo/anúncio criado por este sistema nasce PAUSED nos 3
    níveis (segurança contra ativação acidental) — resume_campaign precisa
    reativar TODOS os níveis, não só a campanha, senão o Google Ads mostra
    "Not eligible: all ad groups/ads are paused" mesmo com campaign.status
    ENABLED (bug real observado em produção).
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Canil Resume')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='2059070343')

    def test_dry_run_does_not_call_the_api(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().resume_campaign(self.account, 'ext-1')
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_resume_enables_campaign_ad_groups_and_ads(self, mock_request):
        def fake_request(method, account, path, **kwargs):
            if path.endswith('campaigns:mutate'):
                return {'results': [{}]}
            if path.endswith('adGroups:mutate'):
                return {'results': [{}]}
            if path.endswith('adGroupAds:mutate'):
                return {'results': [{}]}
            if path.endswith('googleAds:search'):
                query = kwargs['json']['query']
                if 'FROM ad_group_ad' in query:
                    return {'results': [{'adGroupAd': {'resourceName': 'customers/2059070343/adGroupAds/1~1'}}]}
                if 'FROM ad_group ' in query:
                    return {'results': [{'adGroup': {'resourceName': 'customers/2059070343/adGroups/1'}}]}
            raise AssertionError(f'unexpected call: {path} {kwargs}')

        mock_request.side_effect = fake_request
        GoogleAdsProvider().resume_campaign(self.account, '123')

        called_paths = [call.args[2] for call in mock_request.call_args_list]
        self.assertIn('customers/2059070343/campaigns:mutate', called_paths)
        self.assertIn('customers/2059070343/adGroups:mutate', called_paths)
        self.assertIn('customers/2059070343/adGroupAds:mutate', called_paths)

        ad_group_mutate = next(c for c in mock_request.call_args_list if c.args[2] == 'customers/2059070343/adGroups:mutate')
        self.assertEqual(ad_group_mutate.kwargs['json']['operations'][0]['update']['status'], 'ENABLED')
        ad_mutate = next(c for c in mock_request.call_args_list if c.args[2] == 'customers/2059070343/adGroupAds:mutate')
        self.assertEqual(ad_mutate.kwargs['json']['operations'][0]['update']['status'], 'ENABLED')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_resume_skips_mutate_calls_when_nothing_is_paused(self, mock_request):
        def fake_request(method, account, path, **kwargs):
            if path.endswith('campaigns:mutate'):
                return {'results': [{}]}
            if path.endswith('googleAds:search'):
                return {'results': []}  # nada PAUSED
            raise AssertionError(f'unexpected call: {path}')

        mock_request.side_effect = fake_request
        GoogleAdsProvider().resume_campaign(self.account, '123')

        called_paths = [call.args[2] for call in mock_request.call_args_list]
        self.assertNotIn('customers/2059070343/adGroups:mutate', called_paths)
        self.assertNotIn('customers/2059070343/adGroupAds:mutate', called_paths)


class UploadConversionDataManagerTests(TestCase):
    """
    upload_conversion migrou de customers/{id}:uploadClickConversions (Google Ads
    API, descontinuada para novos adotantes desde 2026-06-15) para a Data Manager
    API (events:ingest) — endpoint/host/payload completamente diferentes.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Canil DM')
        self.account = AdvertisingAccount.objects.create(
            organization=self.org, customer_id='2059070343', login_customer_id='1717587348',
        )

    def test_dry_run_never_calls_data_manager(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request') as mock_dm:
            result = GoogleAdsProvider().upload_conversion(self.account, ConversionSpec(
                conversion_action='customers/2059070343/conversionActions/111', gclid='g1',
            ))
        mock_dm.assert_not_called()
        self.assertTrue(result.success)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request')
    def test_sends_events_ingest_with_numeric_conversion_action_and_login_account(self, mock_dm):
        mock_dm.return_value = {'ok': True}
        GoogleAdsProvider().upload_conversion(self.account, ConversionSpec(
            conversion_action='customers/2059070343/conversionActions/111', gclid='g1',
            conversion_value=250.0, currency='BRL', event_id='evt-1',
        ))

        args, kwargs = mock_dm.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(args[2], 'events:ingest')
        payload = kwargs['json']
        destination = payload['destinations'][0]
        self.assertEqual(destination['productDestinationId'], '111')  # ID numérico, não o resource name
        self.assertEqual(destination['operatingAccount'], {'accountType': 'GOOGLE_ADS', 'accountId': '2059070343'})
        self.assertEqual(destination['loginAccount'], {'accountType': 'GOOGLE_ADS', 'accountId': '1717587348'})
        event = payload['events'][0]
        self.assertEqual(event['adIdentifiers'], {'gclid': 'g1'})
        self.assertEqual(event['conversionValue'], 250.0)
        self.assertEqual(event['transactionId'], 'evt-1')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request')
    def test_falls_back_to_gbraid_then_wbraid_when_no_gclid(self, mock_dm):
        mock_dm.return_value = {'ok': True}
        GoogleAdsProvider().upload_conversion(self.account, ConversionSpec(
            conversion_action='customers/2059070343/conversionActions/111', gclid='', gbraid='gb-1', wbraid='wb-1',
        ))
        event = mock_dm.call_args[1]['json']['events'][0]
        self.assertEqual(event['adIdentifiers'], {'gbraid': 'gb-1'})

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    def test_no_click_identifier_fails_without_calling_api(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request') as mock_dm:
            result = GoogleAdsProvider().upload_conversion(self.account, ConversionSpec(
                conversion_action='customers/2059070343/conversionActions/111', gclid='',
            ))
        mock_dm.assert_not_called()
        self.assertFalse(result.success)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request')
    def test_phone_is_never_sent_in_plain_text_always_hashed_after_e164_normalization(self, mock_dm):
        import hashlib
        mock_dm.return_value = {'ok': True}
        GoogleAdsProvider().upload_conversion(self.account, ConversionSpec(
            conversion_action='customers/2059070343/conversionActions/111', gclid='g1', phone='(48) 99999-1111',
        ))
        payload = mock_dm.call_args[1]['json']
        expected_hash = hashlib.sha256('+5548999991111'.encode('utf-8')).hexdigest()
        sent_phone = payload['events'][0]['userData']['userIdentifiers'][0]['phoneNumber']
        self.assertEqual(sent_phone, expected_hash)
        self.assertNotIn('99999-1111', str(payload))  # nunca em texto puro
        self.assertEqual(payload['encoding'], 'HEX')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._data_manager_request')
    def test_no_login_account_when_operating_account_is_not_managed_by_mcc(self, mock_dm):
        account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9990001111')
        mock_dm.return_value = {'ok': True}
        GoogleAdsProvider().upload_conversion(account, ConversionSpec(
            conversion_action='customers/9990001111/conversionActions/222', gclid='g1',
        ))
        destination = mock_dm.call_args[1]['json']['destinations'][0]
        self.assertNotIn('loginAccount', destination)
