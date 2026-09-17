from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdAgentDecision
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.providers.base import ProviderCampaign
from apps.advertising.services.campaign_service import CampaignService

AD_GROUPS_DATA = [
    {
        'name': 'Comprar',
        'keywords': [{'text': 'comprar border collie', 'match_type': 'EXACT'}],
        'ads': [{'headlines': ['Filhotes Border Collie'], 'descriptions': ['Conheça a ninhada.']}],
    },
    {
        'name': 'Preço',
        'keywords': [{'text': 'border collie preço', 'match_type': 'EXACT'}],
        'ads': [{'headlines': ['Consulte Disponibilidade'], 'descriptions': ['Veja fotos e informações.']}],
    },
]


class CampaignServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil E')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1231231234')
        self.data = {'name': 'Ninhada Border Collie Agosto', 'daily_budget': 20}

    @override_settings(GOOGLE_ADS_ENABLED=False)
    def test_create_campaign_stays_draft_when_globally_disabled(self):
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'draft')
        self.assertIn('desabilitado', campaign.error_message)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_success_marks_active(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-123', status='active')
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'active')
        self.assertEqual(campaign.external_campaign_id, 'dryrun-123')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_provider_error_is_captured_never_raised(self, mock_create):
        mock_create.side_effect = GoogleAdsProviderError('Conta suspensa pelo Google.', code='account_suspended')
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None, data=self.data,
        )
        self.assertEqual(campaign.status, 'error')
        self.assertEqual(campaign.error_message, 'Conta suspensa pelo Google.')

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_is_idempotent_via_client_request_id(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-abc', status='active')
        service = CampaignService()
        first = service.create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data=self.data, client_request_id='req-1',
        )
        second = service.create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data=self.data, client_request_id='req-1',
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(AdCampaign.objects.filter(client_request_id='req-1').count(), 1)
        mock_create.assert_called_once()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.resume_campaign')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.pause_campaign')
    def test_pause_and_resume_campaign(self, mock_pause, mock_resume):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X',
            daily_budget=10, status='active', external_campaign_id='ext-1',
        )
        service = CampaignService()

        paused = service.pause_campaign(self.org, campaign.id)
        self.assertEqual(paused.status, 'paused')
        mock_pause.assert_called_once()

        resumed = service.resume_campaign(self.org, campaign.id)
        self.assertEqual(resumed.status, 'active')
        mock_resume.assert_called_once()

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_with_ad_groups_aggregates_legacy_flat_fields(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-ag', status='active')
        campaign = CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data={**self.data, 'ad_groups': AD_GROUPS_DATA},
        )

        self.assertEqual(set(campaign.ad_keywords), {'comprar border collie', 'border collie preço'})
        self.assertEqual(set(campaign.ad_headlines), {'Filhotes Border Collie', 'Consulte Disponibilidade'})

        spec = mock_create.call_args[0][1]
        self.assertEqual(len(spec.ad_groups), 2)
        self.assertEqual(spec.ad_groups[0].keywords[0].match_type, 'EXACT')
        # Campos legados da spec ficam vazios quando ad_groups é usado — evita duplicar
        # keywords/anúncios num "grupo fantasma" além dos definidos em ad_groups.
        self.assertEqual(spec.keywords, [])

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_applies_safety_net_bid_when_none_given(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-bid', status='active')
        CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data={**self.data, 'ad_groups': AD_GROUPS_DATA},
        )
        spec = mock_create.call_args[0][1]
        self.assertEqual(spec.default_cpc_bid, 1.0)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_campaign')
    def test_create_campaign_respects_explicit_default_cpc_bid(self, mock_create):
        mock_create.return_value = ProviderCampaign(external_id='dryrun-bid2', status='active')
        CampaignService().create_campaign(
            organization=self.org, advertising_account=self.account, litter=None,
            data={**self.data, 'ad_groups': AD_GROUPS_DATA, 'default_cpc_bid': 3.5},
        )
        spec = mock_create.call_args[0][1]
        self.assertEqual(spec.default_cpc_bid, 3.5)

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.add_location_targeting')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_location_criteria')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.suggest_geo_target_constants')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.remove_location_criteria')
    def test_update_geo_targeting_removes_and_adds_cities_and_logs_decision(
        self, mock_remove, mock_suggest, mock_list_criteria, mock_add,
    ):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X', daily_budget=40,
            status='active', external_campaign_id='ext-1',
            region='Florianópolis, Biguaçu, Itajaí',
        )
        mock_suggest.return_value = ['geoTargetConstants/9999']  # id de "Biguaçu"
        mock_list_criteria.return_value = [
            {'resource_name': 'customers/1/campaignCriteria/1~1', 'geo_target_constant': 'geoTargetConstants/9999'},
            {'resource_name': 'customers/1/campaignCriteria/1~2', 'geo_target_constant': 'geoTargetConstants/1111'},
        ]

        result = CampaignService().update_geo_targeting(
            self.org, campaign.id, remove_cities=['Biguaçu'], add_cities=['Itapema'],
            reason='Alinhar com o playbook revisado.',
        )

        mock_remove.assert_called_once_with(self.account, ['customers/1/campaignCriteria/1~1'])
        mock_add.assert_called_once_with(self.account, f'customers/{self.account.customer_id}/campaigns/ext-1', 'Itapema')
        self.assertEqual(result.region, 'Florianópolis, Itajaí, Itapema')

        decision = AdAgentDecision.objects.get(campaign=campaign, action='update_geo_targeting')
        self.assertEqual(decision.before, {'region': 'Florianópolis, Biguaçu, Itajaí'})
        self.assertEqual(decision.after, {'region': 'Florianópolis, Itajaí, Itapema'})

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_group_cpc_bid')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_set_ad_group_cpc_bids_fixes_all_ad_groups_and_logs_decision(self, mock_list, mock_set_bid):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X',
            daily_budget=40, status='active', external_campaign_id='ext-1',
        )
        mock_list.return_value = [
            {'resource_name': 'customers/1/adGroups/1', 'name': 'Comprar', 'cpc_bid_micros': 10000},
            {'resource_name': 'customers/1/adGroups/2', 'name': 'Preço', 'cpc_bid_micros': 10000},
        ]

        CampaignService().set_ad_group_cpc_bids(self.org, campaign.id, 2.5, reason='CPC estava em 1 centavo.')

        self.assertEqual(mock_set_bid.call_count, 2)
        mock_set_bid.assert_any_call(self.account, 'customers/1/adGroups/1', 2.5)
        decision = AdAgentDecision.objects.get(campaign=campaign, action='set_ad_group_cpc_bids')
        self.assertEqual(decision.before, {'Comprar': 0.01, 'Preço': 0.01})
        self.assertEqual(decision.after, {'cpc_bid': 2.5})

    @override_settings(GOOGLE_ADS_ENABLED=True, GOOGLE_ADS_DRY_RUN=True)
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.pause_campaign')
    def test_pause_campaign_logs_decision_with_real_metrics_snapshot(self, mock_pause):
        campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='X',
            daily_budget=10, status='active', external_campaign_id='ext-1',
        )
        CampaignService().pause_campaign(self.org, campaign.id, reason='teste')

        decision = AdAgentDecision.objects.get(campaign=campaign, action='pause_campaign')
        self.assertTrue(decision.metrics_snapshot)
        self.assertIn('cost', decision.metrics_snapshot)
        self.assertIn('qualified_leads', decision.metrics_snapshot)
        self.assertEqual(decision.metrics_snapshot['campaign_id'], campaign.id)


class WriteToolsTests(TestCase):
    """add_keywords / set_keyword_status / create_ad_group / update_bidding_strategy — resolvem o
    ad group/keyword alvo por nome via a API (não há AdGroup/Keyword local), e tratam ambiguidade
    (mais de um match) como erro explícito em vez de adivinhar."""

    def setUp(self):
        self.org = Organization.objects.create(name='Canil W')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1112223335')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Campanha X',
            daily_budget=40, status='active', external_campaign_id='ext-1',
        )

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.add_keywords')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_add_keywords_resolves_ad_group_by_partial_name(self, mock_list, mock_add):
        mock_list.return_value = [
            {'resource_name': 'customers/1/adGroups/1', 'name': 'Campanha X — Comprar', 'cpc_bid_micros': 2_500_000},
            {'resource_name': 'customers/1/adGroups/2', 'name': 'Campanha X — Preço', 'cpc_bid_micros': 2_500_000},
        ]
        campaign = CampaignService().add_keywords(
            self.org, self.campaign.id, 'Comprar', [{'text': 'border collie filhote', 'match_type': 'EXACT'}],
        )
        self.assertEqual(campaign.error_message, '')
        mock_add.assert_called_once()
        self.assertEqual(mock_add.call_args.args[1], 'customers/1/adGroups/1')
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='add_keywords')
        self.assertEqual(decision.after['ad_group'], 'Campanha X — Comprar')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_add_keywords_ambiguous_name_is_reported_never_guessed(self, mock_list):
        mock_list.return_value = [
            {'resource_name': 'customers/1/adGroups/1', 'name': 'Campanha X — Comprar SC', 'cpc_bid_micros': 0},
            {'resource_name': 'customers/1/adGroups/2', 'name': 'Campanha X — Comprar Preço', 'cpc_bid_micros': 0},
        ]
        campaign = CampaignService().add_keywords(self.org, self.campaign.id, 'Comprar', [{'text': 'x'}])
        self.assertIn('Mais de um ad group', campaign.error_message)

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_add_keywords_no_match_is_reported(self, mock_list):
        mock_list.return_value = []
        campaign = CampaignService().add_keywords(self.org, self.campaign.id, 'Inexistente', [{'text': 'x'}])
        self.assertIn('Nenhum ad group encontrado', campaign.error_message)

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_keyword_status')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_keywords')
    def test_set_keyword_status_pauses_matched_keyword(self, mock_list, mock_set_status):
        mock_list.return_value = [
            {'resource_name': 'customers/1/adGroupCriteria/1~1', 'text': 'border collie preço',
             'match_type': 'EXACT', 'status': 'ENABLED', 'ad_group_name': 'Preço'},
        ]
        campaign = CampaignService().set_keyword_status(self.org, self.campaign.id, 'border collie preço', 'PAUSED')
        self.assertEqual(campaign.error_message, '')
        mock_set_status.assert_called_once_with(self.account, 'customers/1/adGroupCriteria/1~1', 'PAUSED')
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='set_keyword_status')
        self.assertEqual(
            decision.before,
            {'keyword': 'border collie preço', 'keyword_id': '1~1', 'previous_status': 'ENABLED'},
        )

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_keywords')
    def test_set_keyword_status_ambiguous_without_match_type_is_reported(self, mock_list):
        mock_list.return_value = [
            {'resource_name': 'r1', 'text': 'border collie', 'match_type': 'EXACT', 'status': 'ENABLED', 'ad_group_name': 'A'},
            {'resource_name': 'r2', 'text': 'border collie', 'match_type': 'PHRASE', 'status': 'ENABLED', 'ad_group_name': 'B'},
        ]
        campaign = CampaignService().set_keyword_status(self.org, self.campaign.id, 'border collie', 'PAUSED')
        self.assertIn('Informe match_type', campaign.error_message)

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_keywords')
    def test_set_keyword_status_match_type_disambiguates(self, mock_list):
        mock_list.return_value = [
            {'resource_name': 'r1', 'text': 'border collie', 'match_type': 'EXACT', 'status': 'ENABLED', 'ad_group_name': 'A'},
            {'resource_name': 'r2', 'text': 'border collie', 'match_type': 'PHRASE', 'status': 'ENABLED', 'ad_group_name': 'B'},
        ]
        with patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_keyword_status') as mock_set_status:
            campaign = CampaignService().set_keyword_status(
                self.org, self.campaign.id, 'border collie', 'PAUSED', match_type='PHRASE',
            )
        self.assertEqual(campaign.error_message, '')
        mock_set_status.assert_called_once_with(self.account, 'r2', 'PAUSED')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_ad_group')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_create_ad_group_inherits_existing_cpc_bid_when_not_given(self, mock_list, mock_create):
        mock_list.return_value = [
            {'resource_name': 'customers/1/adGroups/1', 'name': 'Comprar', 'cpc_bid_micros': 2_500_000},
        ]
        mock_create.return_value = 'customers/1/adGroups/99'
        campaign = CampaignService().create_ad_group(
            self.org, self.campaign.id, 'Teste Curitiba',
            keywords=[{'text': 'border collie curitiba', 'match_type': 'EXACT'}],
            ads=[{'headlines': ['H1'], 'descriptions': ['D1']}],
        )
        self.assertEqual(campaign.error_message, '')
        self.assertEqual(mock_create.call_args.kwargs['cpc_bid'], 2.5)
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='create_ad_group')
        self.assertEqual(decision.after['ad_group_name'], 'Teste Curitiba')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.update_bidding_strategy')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.get_bidding_strategy_type')
    def test_update_bidding_strategy_logs_before_and_after(self, mock_get_type, mock_update):
        mock_get_type.return_value = 'MANUAL_CPC'
        campaign = CampaignService().update_bidding_strategy(
            self.org, self.campaign.id, 'MAXIMIZE_CONVERSIONS',
            reason='Volume de conversão suficiente após 7 dias.', performed_by='agent',
            approval_status='confirmed_by_user',
        )
        self.assertEqual(campaign.error_message, '')
        mock_update.assert_called_once_with(self.account, 'ext-1', 'MAXIMIZE_CONVERSIONS', target_cpa=None)
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='update_bidding_strategy')
        self.assertEqual(decision.before, {'bidding_strategy_type': 'MANUAL_CPC'})
        self.assertEqual(decision.after, {'bidding_strategy_type': 'MAXIMIZE_CONVERSIONS', 'target_cpa': None})
        self.assertEqual(decision.approval_status, 'confirmed_by_user')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.update_bidding_strategy')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.get_bidding_strategy_type')
    def test_update_bidding_strategy_provider_error_is_captured(self, mock_get_type, mock_update):
        mock_get_type.return_value = 'MANUAL_CPC'
        mock_update.side_effect = GoogleAdsProviderError('Conta suspensa pelo Google.')
        campaign = CampaignService().update_bidding_strategy(self.org, self.campaign.id, 'TARGET_CPA', target_cpa=20)
        self.assertEqual(campaign.error_message, 'Conta suspensa pelo Google.')
        self.assertFalse(AdAgentDecision.objects.filter(campaign=self.campaign, action='update_bidding_strategy').exists())

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.create_responsive_search_ad')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_add_responsive_search_ad_resolves_ad_group_and_logs_decision(self, mock_list, mock_create_rsa):
        mock_list.return_value = [{'resource_name': 'customers/1/adGroups/1', 'name': 'Comprar', 'cpc_bid_micros': 2_500_000}]
        campaign = CampaignService().add_responsive_search_ad(
            self.org, self.campaign.id, 'Comprar', ['H1', 'H2'], ['D1'],
            reason='Reposicionar mensagem para procedência/linhagem.',
        )
        self.assertEqual(campaign.error_message, '')
        mock_create_rsa.assert_called_once_with(
            self.account, 'customers/1/adGroups/1', self.campaign.landing_url, headlines=['H1', 'H2'], descriptions=['D1'],
        )
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='add_responsive_search_ad')
        self.assertEqual(decision.after['ad_group'], 'Comprar')
        self.assertEqual(decision.after['headlines'], ['H1', 'H2'])

    def test_add_responsive_search_ad_rejects_headline_over_limit_without_truncating(self):
        from apps.advertising.services.campaign_service import AssetLengthError
        with self.assertRaises(AssetLengthError):
            CampaignService().add_responsive_search_ad(
                self.org, self.campaign.id, 'Comprar', ['H' * 31], ['D1'],
            )

    def test_add_responsive_search_ad_rejects_description_over_limit_without_truncating(self):
        from apps.advertising.services.campaign_service import AssetLengthError
        with self.assertRaises(AssetLengthError):
            CampaignService().add_responsive_search_ad(
                self.org, self.campaign.id, 'Comprar', ['H1'], ['D' * 91],
            )

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.list_ad_groups')
    def test_add_responsive_search_ad_no_matching_group_is_reported(self, mock_list):
        mock_list.return_value = []
        campaign = CampaignService().add_responsive_search_ad(self.org, self.campaign.id, 'Inexistente', ['H1'], ['D1'])
        self.assertIn('Nenhum ad group encontrado', campaign.error_message)

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_status')
    def test_set_ad_status_logs_decision(self, mock_set_status):
        campaign = CampaignService().set_ad_status(
            self.org, self.campaign.id, 'customers/1/adGroupAds/1~1', 'PAUSED',
            reason='Substituído por RSA com nova mensagem.',
        )
        self.assertEqual(campaign.error_message, '')
        mock_set_status.assert_called_once_with(self.account, 'customers/1/adGroupAds/1~1', 'PAUSED')
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='set_ad_status')
        self.assertEqual(decision.after, {'ad_resource_name': 'customers/1/adGroupAds/1~1', 'status': 'PAUSED'})

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_status')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_group_status')
    def test_set_ad_status_enabled_also_enables_the_ad_group(self, mock_set_group_status, mock_set_status):
        """Regressão: um ad group novo (via create_ad_group) sempre nasce PAUSED — ativar só o
        anúncio e esquecer do grupo deixa tudo parado silenciosamente (bug real observado)."""
        campaign = CampaignService().set_ad_status(
            self.org, self.campaign.id, 'customers/1112223335/adGroupAds/555~1', 'ENABLED',
        )
        self.assertEqual(campaign.error_message, '')
        mock_set_group_status.assert_called_once_with(self.account, 'customers/1112223335/adGroups/555', 'ENABLED')
        mock_set_status.assert_called_once_with(self.account, 'customers/1112223335/adGroupAds/555~1', 'ENABLED')

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_status')
    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.set_ad_group_status')
    def test_set_ad_status_paused_does_not_touch_the_ad_group(self, mock_set_group_status, mock_set_status):
        CampaignService().set_ad_status(self.org, self.campaign.id, 'customers/1112223335/adGroupAds/555~1', 'PAUSED')
        mock_set_group_status.assert_not_called()

    @patch('apps.advertising.providers.google_ads.GoogleAdsProvider.update_ad_content')
    def test_update_ad_content_by_resource_edits_a_specific_ad_and_logs_decision(self, mock_update):
        campaign = CampaignService().update_ad_content_by_resource(
            self.org, self.campaign.id, 'customers/1112223335/adGroupAds/555~1',
            ['H1', 'H2'], ['D1'], reason='Melhorar Ad Strength (estava POOR).',
        )
        self.assertEqual(campaign.error_message, '')
        mock_update.assert_called_once_with(self.account, 'customers/1112223335/adGroupAds/555~1', ['H1', 'H2'], ['D1'])
        decision = AdAgentDecision.objects.get(campaign=self.campaign, action='update_ad_content_by_resource')
        self.assertEqual(decision.after['headlines'], ['H1', 'H2'])
        # Não mexe no resumo agregado legado da campanha.
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.ad_headlines, [])

    def test_update_ad_content_by_resource_rejects_headline_over_limit(self):
        from apps.advertising.services.campaign_service import AssetLengthError
        with self.assertRaises(AssetLengthError):
            CampaignService().update_ad_content_by_resource(
                self.org, self.campaign.id, 'customers/1112223335/adGroupAds/555~1', ['H' * 31], ['D1'],
            )
