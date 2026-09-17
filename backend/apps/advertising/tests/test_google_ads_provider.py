from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount
from apps.advertising.providers.base import ConversionSpec, CampaignSpec, AdGroupSpec, AdContentSpec, KeywordSpec
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


class LocationCriteriaManagementTests(TestCase):
    """Não existe "atualizar" localização na Google Ads API — trocar geografia de uma campanha
    já criada exige listar os critérios ativos, remover os indesejados e criar os novos."""

    def setUp(self):
        self.org = Organization.objects.create(name='Canil Geo')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='5556667778')

    def test_list_location_criteria_returns_empty_in_dry_run(self):
        result = GoogleAdsProvider().list_location_criteria(self.account, 'ext-1')
        self.assertEqual(result, [])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_list_location_criteria_parses_response(self, mock_request):
        mock_request.return_value = {'results': [
            {'campaignCriterion': {
                'resourceName': 'customers/5556667778/campaignCriteria/1~2',
                'location': {'geoTargetConstant': 'geoTargetConstants/1001'},
            }},
        ]}
        result = GoogleAdsProvider().list_location_criteria(self.account, 'ext-1')
        self.assertEqual(result, [{
            'resource_name': 'customers/5556667778/campaignCriteria/1~2',
            'geo_target_constant': 'geoTargetConstants/1001',
        }])

    def test_remove_location_criteria_noop_with_empty_list(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().remove_location_criteria(self.account, [])
        mock_request.assert_not_called()

    def test_remove_location_criteria_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().remove_location_criteria(self.account, ['customers/5556667778/campaignCriteria/1~2'])
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_remove_location_criteria_sends_remove_operations(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().remove_location_criteria(self.account, [
            'customers/5556667778/campaignCriteria/1~2', 'customers/5556667778/campaignCriteria/1~3',
        ])
        args, kwargs = mock_request.call_args
        self.assertEqual(args[2], 'customers/5556667778/campaignCriteria:mutate')
        operations = kwargs['json']['operations']
        self.assertEqual(operations, [
            {'remove': 'customers/5556667778/campaignCriteria/1~2'},
            {'remove': 'customers/5556667778/campaignCriteria/1~3'},
        ])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.suggest_geo_target_constants')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_add_location_targeting_creates_criteria(self, mock_request, mock_suggest):
        mock_suggest.return_value = ['geoTargetConstants/2001']
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().add_location_targeting(self.account, 'customers/5556667778/campaigns/1', 'Itapema')
        operations = mock_request.call_args.kwargs['json']['operations']
        self.assertEqual(operations[0]['create']['location'], {'geoTargetConstant': 'geoTargetConstants/2001'})

    def test_add_location_targeting_noop_in_dry_run(self):
        """Regressão: sendo um ponto de entrada próprio (não só chamado de dentro de
        create_campaign, que já checa _is_live() antes), precisa checar sozinho — sem isso, faria
        uma chamada real à API mesmo com GOOGLE_ADS_DRY_RUN=True."""
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().add_location_targeting(self.account, 'customers/1112223334/campaigns/1', 'Itapema')
        mock_request.assert_not_called()


class KeywordAndAdGroupWriteToolsTests(TestCase):
    """Ferramentas de escrita que faltavam: adicionar keyword a ad group existente, pausar/reativar
    keyword individual, criar ad group novo numa campanha já existente, trocar bidding strategy."""

    def setUp(self):
        self.org = Organization.objects.create(name='Canil W')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='7778889990')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_add_keywords_sends_correct_match_types(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().add_keywords(self.account, 'customers/7778889990/adGroups/1', [
            KeywordSpec(text='border collie preço', match_type='EXACT'),
        ])
        operations = mock_request.call_args.kwargs['json']['operations']
        self.assertEqual(operations[0]['create']['keyword'], {'text': 'border collie preço', 'matchType': 'EXACT'})

    def test_add_keywords_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().add_keywords(self.account, 'customers/7778889990/adGroups/1', [KeywordSpec(text='x')])
        mock_request.assert_not_called()

    def test_list_keywords_returns_empty_in_dry_run(self):
        result = GoogleAdsProvider().list_keywords(self.account, 'ext-1')
        self.assertEqual(result, [])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_list_keywords_parses_response(self, mock_request):
        mock_request.return_value = {'results': [{
            'adGroupCriterion': {
                'resourceName': 'customers/7778889990/adGroupCriteria/1~1',
                'keyword': {'text': 'border collie sc', 'matchType': 'EXACT'},
                'status': 'ENABLED',
            },
            'adGroup': {'name': 'Comprar'},
        }]}
        result = GoogleAdsProvider().list_keywords(self.account, 'ext-1')
        self.assertEqual(result, [{
            'resource_name': 'customers/7778889990/adGroupCriteria/1~1',
            'text': 'border collie sc', 'match_type': 'EXACT', 'status': 'ENABLED', 'ad_group_name': 'Comprar',
        }])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_set_keyword_status_sends_update(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().set_keyword_status(self.account, 'customers/7778889990/adGroupCriteria/1~1', 'PAUSED')
        op = mock_request.call_args.kwargs['json']['operations'][0]['update']
        self.assertEqual(op, {'resourceName': 'customers/7778889990/adGroupCriteria/1~1', 'status': 'PAUSED'})

    def test_set_keyword_status_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().set_keyword_status(self.account, 'customers/7778889990/adGroupCriteria/1~1', 'PAUSED')
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_create_ad_group_creates_group_keywords_and_ads(self, mock_request):
        def fake(method, account, path, **kwargs):
            if path.endswith('adGroups:mutate'):
                return {'results': [{'resourceName': 'customers/7778889990/adGroups/99'}]}
            return {'results': []}
        mock_request.side_effect = fake

        resource_name = GoogleAdsProvider().create_ad_group(
            self.account, 'customers/7778889990/campaigns/1', 'Campanha X',
            ad_group_name='Teste Curitiba',
            keywords=[KeywordSpec(text='border collie curitiba', match_type='EXACT')],
            ads=[AdContentSpec(headlines=['H1'], descriptions=['D1'])],
            landing_url='https://example.com', cpc_bid=3.0,
        )
        self.assertEqual(resource_name, 'customers/7778889990/adGroups/99')

        ad_group_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('adGroups:mutate'))
        create_payload = ad_group_call.kwargs['json']['operations'][0]['create']
        self.assertEqual(create_payload['name'], 'Campanha X — Teste Curitiba')
        self.assertEqual(create_payload['cpcBidMicros'], 3_000_000)

        keyword_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('adGroupCriteria:mutate'))
        self.assertEqual(keyword_call.kwargs['json']['operations'][0]['create']['keyword']['matchType'], 'EXACT')

        ad_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('adGroupAds:mutate'))
        self.assertEqual(ad_call.kwargs['json']['operations'][0]['create']['ad']['finalUrls'], ['https://example.com'])

    def test_create_ad_group_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            resource_name = GoogleAdsProvider().create_ad_group(
                self.account, 'customers/7778889990/campaigns/1', 'Campanha X',
                ad_group_name='Teste', keywords=[], ads=[],
            )
        mock_request.assert_not_called()
        self.assertTrue(resource_name.startswith('customers/7778889990/campaigns/1/adGroups/dryrun-'))

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_create_responsive_search_ad_adds_rsa_to_existing_group(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().create_responsive_search_ad(
            self.account, 'customers/7778889990/adGroups/1', 'https://example.com',
            headlines=['H1', 'H2'], descriptions=['D1'],
        )
        op = mock_request.call_args.kwargs['json']['operations'][0]['create']
        self.assertEqual(op['adGroup'], 'customers/7778889990/adGroups/1')
        self.assertEqual(op['status'], 'PAUSED')
        self.assertEqual([h['text'] for h in op['ad']['responsiveSearchAd']['headlines']], ['H1', 'H2'])
        self.assertEqual(op['ad']['finalUrls'], ['https://example.com'])

    def test_create_responsive_search_ad_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().create_responsive_search_ad(
                self.account, 'customers/7778889990/adGroups/1', 'https://example.com',
                headlines=['H1'], descriptions=['D1'],
            )
        mock_request.assert_not_called()

    def test_list_ads_returns_empty_in_dry_run(self):
        self.assertEqual(GoogleAdsProvider().list_ads(self.account, 'ext-1'), [])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_list_ads_parses_response(self, mock_request):
        mock_request.return_value = {'results': [{
            'adGroupAd': {
                'resourceName': 'customers/7778889990/adGroupAds/1~1', 'status': 'ENABLED',
                'ad': {'responsiveSearchAd': {'headlines': [{'text': 'H1'}], 'descriptions': [{'text': 'D1'}]}},
            },
            'adGroup': {'name': 'Comprar', 'id': '1'},
        }]}
        result = GoogleAdsProvider().list_ads(self.account, 'ext-1')
        self.assertEqual(result, [{
            'resource_name': 'customers/7778889990/adGroupAds/1~1', 'status': 'ENABLED',
            'ad_group_name': 'Comprar', 'ad_group_id': '1', 'headlines': ['H1'], 'descriptions': ['D1'],
        }])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_set_ad_status_sends_update(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().set_ad_status(self.account, 'customers/7778889990/adGroupAds/1~1', 'PAUSED')
        op = mock_request.call_args.kwargs['json']['operations'][0]['update']
        self.assertEqual(op, {'resourceName': 'customers/7778889990/adGroupAds/1~1', 'status': 'PAUSED'})

    def test_set_ad_status_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().set_ad_status(self.account, 'customers/7778889990/adGroupAds/1~1', 'PAUSED')
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_set_ad_group_status_sends_update(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().set_ad_group_status(self.account, 'customers/7778889990/adGroups/1', 'ENABLED')
        op = mock_request.call_args.kwargs['json']['operations'][0]['update']
        self.assertEqual(op, {'resourceName': 'customers/7778889990/adGroups/1', 'status': 'ENABLED'})

    def test_set_ad_group_status_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().set_ad_group_status(self.account, 'customers/7778889990/adGroups/1', 'ENABLED')
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_update_bidding_strategy_manual_cpc(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().update_bidding_strategy(self.account, 'ext-1', 'MANUAL_CPC')
        op = mock_request.call_args.kwargs['json']['operations'][0]
        self.assertEqual(op['update']['manualCpc'], {})
        self.assertEqual(op['updateMask'], 'manual_cpc')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_update_bidding_strategy_target_cpa(self, mock_request):
        mock_request.return_value = {'results': []}
        GoogleAdsProvider().update_bidding_strategy(self.account, 'ext-1', 'TARGET_CPA', target_cpa=25.0)
        op = mock_request.call_args.kwargs['json']['operations'][0]
        self.assertEqual(op['update']['targetCpa'], {'targetCpaMicros': 25_000_000})

    def test_update_bidding_strategy_target_cpa_without_value_raises(self):
        from apps.advertising.providers.google_ads import GoogleAdsProviderError
        with self.assertRaises(GoogleAdsProviderError):
            GoogleAdsProvider().update_bidding_strategy(self.account, 'ext-1', 'TARGET_CPA')

    def test_update_bidding_strategy_unsupported_raises(self):
        from apps.advertising.providers.google_ads import GoogleAdsProviderError
        with self.assertRaises(GoogleAdsProviderError):
            GoogleAdsProvider().update_bidding_strategy(self.account, 'ext-1', 'TARGET_ROAS')

    def test_update_bidding_strategy_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().update_bidding_strategy(self.account, 'ext-1', 'MANUAL_CPC')
        mock_request.assert_not_called()

    def test_get_bidding_strategy_type_returns_unknown_in_dry_run(self):
        result = GoogleAdsProvider().get_bidding_strategy_type(self.account, 'ext-1')
        self.assertEqual(result, 'UNKNOWN')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_get_bidding_strategy_type_parses_response(self, mock_request):
        mock_request.return_value = {'results': [{'campaign': {'biddingStrategyType': 'MANUAL_CPC'}}]}
        result = GoogleAdsProvider().get_bidding_strategy_type(self.account, 'ext-1')
        self.assertEqual(result, 'MANUAL_CPC')


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


class CreateCampaignMultiAdGroupTests(TestCase):
    """
    CampaignSpec.ad_groups permite criar >1 ad group por campanha, cada um com
    match type real por keyword (não mais Broad fixo) e >=1 RSA — estrutura
    exigida pela campanha "SC | Border Collie | Ninhada Atual | Search".
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Canil M')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='9998887776')

    def _fake_request(self, mock_request, ad_group_names):
        ad_group_counter = {'i': 0}

        def fake(method, account, path, **kwargs):
            if path.endswith('campaignBudgets:mutate'):
                return {'results': [{'resourceName': 'customers/9998887776/campaignBudgets/1'}]}
            if path.endswith('campaigns:mutate'):
                return {'results': [{'resourceName': 'customers/9998887776/campaigns/555'}]}
            if path.endswith('adGroups:mutate'):
                idx = ad_group_counter['i']
                ad_group_counter['i'] += 1
                return {'results': [{'resourceName': f'customers/9998887776/adGroups/{idx}'}]}
            if path.endswith('adGroupCriteria:mutate') or path.endswith('adGroupAds:mutate') or path.endswith('campaignCriteria:mutate'):
                return {'results': []}
            raise AssertionError(f'unexpected call: {path}')

        mock_request.side_effect = fake

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_creates_one_ad_group_per_spec_with_real_match_types(self, mock_request):
        self._fake_request(mock_request, ['Comprar', 'Preço'])
        spec = CampaignSpec(
            name='SC | Border Collie | Ninhada Atual | Search', daily_budget=40.0,
            landing_url='https://www.bordercolliesul.com.br/',
            ad_groups=[
                AdGroupSpec(
                    name='Comprar',
                    keywords=[KeywordSpec(text='comprar border collie', match_type='EXACT'),
                              KeywordSpec(text='comprar border collie', match_type='PHRASE')],
                    ads=[AdContentSpec(headlines=['Filhotes Border Collie'], descriptions=['Conheça a ninhada.']),
                         AdContentSpec(headlines=['Border Collie à Venda'], descriptions=['Fale pelo WhatsApp.'])],
                ),
                AdGroupSpec(
                    name='Preço',
                    keywords=[KeywordSpec(text='border collie preço', match_type='EXACT')],
                    ads=[AdContentSpec(headlines=['Consulte Disponibilidade'], descriptions=['Veja fotos e informações.'])],
                ),
            ],
        )

        GoogleAdsProvider().create_campaign(self.account, spec)

        ad_group_calls = [c for c in mock_request.call_args_list if c.args[2].endswith('adGroups:mutate')]
        self.assertEqual(len(ad_group_calls), 2)
        names = {c.kwargs['json']['operations'][0]['create']['name'] for c in ad_group_calls}
        self.assertEqual(names, {
            'SC | Border Collie | Ninhada Atual | Search — Comprar',
            'SC | Border Collie | Ninhada Atual | Search — Preço',
        })

        keyword_calls = [c for c in mock_request.call_args_list if c.args[2].endswith('adGroupCriteria:mutate')]
        first_group_keywords = keyword_calls[0].kwargs['json']['operations']
        match_types = {op['create']['keyword']['matchType'] for op in first_group_keywords}
        self.assertEqual(match_types, {'EXACT', 'PHRASE'})

        rsa_calls = [c for c in mock_request.call_args_list if c.args[2].endswith('adGroupAds:mutate')]
        self.assertEqual(len(rsa_calls), 3)  # 2 RSAs no 1º grupo + 1 no 2º

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_negative_keywords_grouped_by_match_type(self, mock_request):
        self._fake_request(mock_request, ['Comprar'])
        spec = CampaignSpec(
            name='Campanha X', daily_budget=40.0,
            ad_groups=[AdGroupSpec(name='Comprar', keywords=[KeywordSpec(text='comprar border collie', match_type='EXACT')],
                                    ads=[AdContentSpec(headlines=['H1'], descriptions=['D1'])])],
            negative_keywords=[KeywordSpec(text='adoção'), KeywordSpec(text='grátis'),
                                KeywordSpec(text='comprar border collie barato', match_type='PHRASE')],
        )

        GoogleAdsProvider().create_campaign(self.account, spec)

        negative_calls = [c for c in mock_request.call_args_list if c.args[2].endswith('campaignCriteria:mutate')]
        # Uma chamada por match type presente na lista de negativas (PHRASE e BROAD).
        self.assertEqual(len(negative_calls), 2)
        broad_call = next(c for c in negative_calls if c.kwargs['json']['operations'][0]['create']['keyword']['matchType'] == 'BROAD')
        broad_texts = {op['create']['keyword']['text'] for op in broad_call.kwargs['json']['operations']}
        self.assertEqual(broad_texts, {'adoção', 'grátis'})

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_geo_target_type_presence_by_default_in_campaign_payload(self, mock_request):
        self._fake_request(mock_request, [])
        spec = CampaignSpec(name='Campanha Y', daily_budget=40.0)

        GoogleAdsProvider().create_campaign(self.account, spec)

        campaign_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('campaigns:mutate'))
        payload = campaign_call.kwargs['json']['operations'][0]['create']
        self.assertEqual(payload['geoTargetTypeSetting'], {'positiveGeoTargetType': 'PRESENCE'})

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_ad_group_cpc_bid_falls_back_to_campaign_default(self, mock_request):
        """
        Sem lance explícito, a Google Ads API cria o ad group com o mínimo técnico (1 centavo),
        inelegível para competir em qualquer leilão real — bug real observado em produção.
        default_cpc_bid garante que todo ad group nasça com um teto de leilão de verdade.
        """
        self._fake_request(mock_request, ['Comprar', 'Preço'])
        spec = CampaignSpec(
            name='Campanha Z', daily_budget=40.0, default_cpc_bid=2.5,
            ad_groups=[
                AdGroupSpec(name='Comprar', keywords=[KeywordSpec(text='k1')],
                            ads=[AdContentSpec(headlines=['H1'], descriptions=['D1'])]),
                AdGroupSpec(name='Preço', keywords=[KeywordSpec(text='k2')], cpc_bid=4.0,
                            ads=[AdContentSpec(headlines=['H2'], descriptions=['D2'])]),
            ],
        )

        GoogleAdsProvider().create_campaign(self.account, spec)

        ad_group_calls = [c for c in mock_request.call_args_list if c.args[2].endswith('adGroups:mutate')]
        bids = {c.kwargs['json']['operations'][0]['create']['name']: c.kwargs['json']['operations'][0]['create']['cpcBidMicros']
                for c in ad_group_calls}
        self.assertEqual(bids['Campanha Z — Comprar'], 2_500_000)  # herdou o default da campanha
        self.assertEqual(bids['Campanha Z — Preço'], 4_000_000)  # cpc_bid próprio do ad group

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_no_cpc_bid_means_no_cpcbidmicros_in_payload(self, mock_request):
        self._fake_request(mock_request, ['Comprar'])
        spec = CampaignSpec(
            name='Campanha W', daily_budget=40.0,
            ad_groups=[AdGroupSpec(name='Comprar', keywords=[KeywordSpec(text='k1')],
                                    ads=[AdContentSpec(headlines=['H1'], descriptions=['D1'])])],
        )
        GoogleAdsProvider().create_campaign(self.account, spec)
        ad_group_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('adGroups:mutate'))
        self.assertNotIn('cpcBidMicros', ad_group_call.kwargs['json']['operations'][0]['create'])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_set_ad_group_cpc_bid_sends_update_payload(self, mock_request):
        mock_request.return_value = {'results': [{}]}
        GoogleAdsProvider().set_ad_group_cpc_bid(self.account, 'customers/9998887776/adGroups/1', 2.5)

        args, kwargs = mock_request.call_args
        self.assertEqual(args[2], 'customers/9998887776/adGroups:mutate')
        operation = kwargs['json']['operations'][0]['update']
        self.assertEqual(operation['resourceName'], 'customers/9998887776/adGroups/1')
        self.assertEqual(operation['cpcBidMicros'], 2_500_000)

    def test_set_ad_group_cpc_bid_noop_in_dry_run(self):
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request') as mock_request:
            GoogleAdsProvider().set_ad_group_cpc_bid(self.account, 'customers/9998887776/adGroups/1', 2.5)
        mock_request.assert_not_called()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_list_ad_groups_parses_response(self, mock_request):
        mock_request.return_value = {'results': [
            {'adGroup': {'resourceName': 'customers/9998887776/adGroups/1', 'name': 'Comprar', 'cpcBidMicros': '10000'}},
        ]}
        result = GoogleAdsProvider().list_ad_groups(self.account, 'ext-1')
        self.assertEqual(result, [{'resource_name': 'customers/9998887776/adGroups/1', 'name': 'Comprar', 'cpc_bid_micros': 10000}])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=False)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider._request')
    def test_legacy_flat_keywords_still_use_broad_when_ad_groups_not_used(self, mock_request):
        self._fake_request(mock_request, [])
        spec = CampaignSpec(
            name='Campanha Legada', daily_budget=20.0,
            keywords=['border collie'], headlines=['H1'], descriptions=['D1'],
        )

        GoogleAdsProvider().create_campaign(self.account, spec)

        keyword_call = next(c for c in mock_request.call_args_list if c.args[2].endswith('adGroupCriteria:mutate'))
        self.assertEqual(keyword_call.kwargs['json']['operations'][0]['create']['keyword']['matchType'], 'BROAD')


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
