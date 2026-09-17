import logging

from django.conf import settings

from apps.advertising.models import AdCampaign, AdAgentDecision
from apps.advertising.providers import GoogleAdsProvider, GoogleAdsProviderError
from apps.advertising.providers.base import CampaignSpec, AdGroupSpec, AdContentSpec, KeywordSpec
from apps.advertising.services.metrics_service import MetricsService

logger = logging.getLogger('apps')

PROVIDERS = {
    'google_ads': GoogleAdsProvider,
}

# Piso de segurança aplicado quando nenhum lance é informado na criação — sem isso, a Google Ads
# API cria o(s) ad group(s) com o mínimo técnico (1 centavo), inelegíveis para competir em
# qualquer leilão real (bug real observado na campanha Border Collie, corrigido ali via
# set_ad_group_cpc_bids). Aplicado aqui, no único ponto de entrada de criação, para que nenhum
# chamador futuro (chat, management command, o que for) possa reintroduzir o mesmo bug.
MINIMUM_SAFE_CPC_BID = 1.0

HEADLINE_MAX_LEN = 30
DESCRIPTION_MAX_LEN = 90


class AssetLengthError(Exception):
    """Um headline/description passado excede o limite do Google Ads — nunca truncamos
    silenciosamente (ver histórico: ai_copy_service já fazia isso e foi identificado como bug)."""


class CampaignService:
    """
    Orquestra a criação/atualização/pausa/retomada de campanhas, delegando a
    operação real de escrita ao AdvertisingProvider do respectivo provider.

    Pensada para ser chamável tanto pela view HTTP quanto, futuramente, por um
    agente de IA (ex.: CampaignService().pause_campaign(org, campaign_id)) sem
    que o chamador precise conhecer o provider ou o model diretamente.
    """

    def _provider(self, provider_name: str):
        provider_cls = PROVIDERS.get(provider_name)
        if not provider_cls:
            raise GoogleAdsProviderError(f'Provider "{provider_name}" não suportado.', code='unsupported_provider')
        return provider_cls()

    def _log_decision(self, campaign, action, before, after, *, reason='', hypothesis='',
                       performed_by='user', approval_status='auto_executed', metrics_snapshot=None):
        AdAgentDecision.objects.create(
            organization=campaign.organization, campaign=campaign, action=action,
            before=before, after=after, reason=reason, hypothesis=hypothesis,
            performed_by=performed_by, approval_status=approval_status,
            metrics_snapshot=metrics_snapshot or {},
        )

    @staticmethod
    def _resource_id(resource_name: str) -> str:
        """Último segmento de um resource name da Google Ads API (ex.:
        'customers/1/adGroups/12345' -> '12345', 'customers/1/adGroupCriteria/12345~678' -> '12345~678')."""
        return (resource_name or '').rstrip('/').split('/')[-1]

    @staticmethod
    def _keyword_specs(raw_keywords: list) -> list[KeywordSpec]:
        specs = []
        for kw in (raw_keywords or []):
            if isinstance(kw, KeywordSpec):
                specs.append(kw)
            elif isinstance(kw, str):
                specs.append(KeywordSpec(text=kw))
            else:
                specs.append(KeywordSpec(text=kw['text'], match_type=kw.get('match_type', 'BROAD')))
        return specs

    @classmethod
    def _ad_group_specs(cls, raw_ad_groups: list) -> list[AdGroupSpec]:
        return [
            AdGroupSpec(
                name=ag['name'],
                keywords=cls._keyword_specs(ag.get('keywords', [])),
                ads=[AdContentSpec(headlines=ad['headlines'], descriptions=ad['descriptions']) for ad in ag.get('ads', [])],
                cpc_bid=ag.get('cpc_bid'),
            )
            for ag in (raw_ad_groups or [])
        ]

    def create_campaign(self, *, organization, advertising_account, litter, data: dict, client_request_id: str | None = None) -> AdCampaign:
        if client_request_id:
            existing = AdCampaign.objects.filter(client_request_id=client_request_id).first()
            if existing:
                return existing

        ad_groups = data.get('ad_groups') or []
        # Campos legados (flat) recebem um resumo agregado de todos os ad groups, para não quebrar
        # telas/ferramentas (update_ad_content, get_campaign_diagnostics) que ainda assumem "a
        # campanha tem 1 anúncio". A estrutura por ad group em si (nome/keywords/RSAs de cada
        # grupo) não é persistida localmente ainda — precisaria de uma migration nova
        # (AdCampaign.ad_groups) que não pôde ser aplicada ao banco de produção nesta sessão; ver
        # limitação documentada no resumo final. O Google Ads é a fonte de verdade da estrutura
        # real criada enquanto isso.
        if ad_groups:
            ad_headlines = [h for ag in ad_groups for ad in ag.get('ads', []) for h in ad['headlines']]
            ad_descriptions = [d for ag in ad_groups for ad in ag.get('ads', []) for d in ad['descriptions']]
            ad_keywords = [
                kw if isinstance(kw, str) else (kw['text'] if isinstance(kw, dict) else kw.text)
                for ag in ad_groups for kw in ag.get('keywords', [])
            ]
        else:
            ad_headlines = data.get('ad_headlines', [])
            ad_descriptions = data.get('ad_descriptions', [])
            ad_keywords = data.get('ad_keywords', [])

        campaign = AdCampaign.objects.create(
            organization=organization,
            advertising_account=advertising_account,
            litter=litter,
            provider=advertising_account.provider,
            name=data['name'],
            daily_budget=data['daily_budget'],
            total_budget=data.get('total_budget'),
            region=data.get('region', ''),
            radius_km=data.get('radius_km'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            landing_url=data.get('landing_url', ''),
            ad_headlines=ad_headlines,
            ad_descriptions=ad_descriptions,
            ad_keywords=ad_keywords,
            client_request_id=client_request_id,
            status='pending',
        )

        if not settings.GOOGLE_ADS_ENABLED:
            campaign.status = 'draft'
            campaign.error_message = 'Omni Ads está desabilitado neste ambiente (GOOGLE_ADS_ENABLED=False).'
            campaign.save(update_fields=['status', 'error_message'])
            return campaign

        default_cpc_bid = data.get('default_cpc_bid')
        if default_cpc_bid is None:
            default_cpc_bid = MINIMUM_SAFE_CPC_BID
            logger.info(
                f'CampaignService.create_campaign: nenhum default_cpc_bid informado — aplicando o '
                f'piso de segurança R$ {MINIMUM_SAFE_CPC_BID:.2f}.'
            )

        spec = CampaignSpec(
            name=campaign.name,
            daily_budget=float(campaign.daily_budget),
            region=campaign.region,
            radius_km=campaign.radius_km,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            landing_url=campaign.landing_url,
            headlines=campaign.ad_headlines if not ad_groups else [],
            descriptions=campaign.ad_descriptions if not ad_groups else [],
            keywords=campaign.ad_keywords if not ad_groups else [],
            ad_groups=self._ad_group_specs(ad_groups),
            negative_keywords=self._keyword_specs(data.get('negative_keywords', [])),
            geo_target_type=data.get('geo_target_type', 'PRESENCE'),
            default_cpc_bid=default_cpc_bid,
        )
        try:
            provider = self._provider(advertising_account.provider)
            result = provider.create_campaign(advertising_account, spec)
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.create_campaign failed')
            campaign.status = 'error'
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['status', 'error_message'])
            return campaign

        campaign.external_campaign_id = result.external_id
        campaign.status = 'active'
        campaign.error_message = result.error_message
        campaign.save(update_fields=['external_campaign_id', 'status', 'error_message'])
        return campaign

    def pause_campaign(self, organization, campaign_id: int, *, reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        before_status = campaign.status
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            self._provider(campaign.provider).pause_campaign(campaign.advertising_account, campaign.external_campaign_id)
            campaign.status = 'paused'
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.pause_campaign failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['status', 'error_message'])
        if campaign.status != before_status:
            self._log_decision(
                campaign, 'pause_campaign', {'status': before_status}, {'status': campaign.status},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
            )
        return campaign

    def resume_campaign(self, organization, campaign_id: int, *, reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        before_status = campaign.status
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            self._provider(campaign.provider).resume_campaign(campaign.advertising_account, campaign.external_campaign_id)
            campaign.status = 'active'
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.resume_campaign failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['status', 'error_message'])
        if campaign.status != before_status:
            self._log_decision(
                campaign, 'resume_campaign', {'status': before_status}, {'status': campaign.status},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
            )
        return campaign

    def update_daily_budget(self, organization, campaign_id: int, new_daily_budget: float, *,
                             reason='', hypothesis='', performed_by='user', approval_status='auto_executed') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        before_budget = campaign.daily_budget
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            spec = CampaignSpec(name=campaign.name, daily_budget=float(new_daily_budget))
            self._provider(campaign.provider).update_campaign(campaign.advertising_account, campaign.external_campaign_id, spec)
            campaign.daily_budget = new_daily_budget
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_daily_budget failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['daily_budget', 'error_message'])
        if campaign.daily_budget != before_budget:
            self._log_decision(
                campaign, 'update_daily_budget',
                {'daily_budget': str(before_budget)}, {'daily_budget': str(campaign.daily_budget)},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by, approval_status=approval_status,
                metrics_snapshot=snapshot,
            )
        return campaign

    def update_geo_targeting(self, organization, campaign_id: int, *, add_cities: list[str] | None = None,
                              remove_cities: list[str] | None = None, reason='', hypothesis='',
                              performed_by='user', approval_status='auto_executed') -> AdCampaign:
        """Ajusta a segmentação geográfica de uma campanha já existente — não existe "atualizar"
        localização na API, só remover critérios antigos e criar novos."""
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        account = campaign.advertising_account
        provider = self._provider(campaign.provider)
        campaign_resource_name = f'customers/{account.customer_id}/campaigns/{campaign.external_campaign_id}'
        before_region = campaign.region
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            if remove_cities:
                remove_geo_ids = set(provider.suggest_geo_target_constants(account, remove_cities))
                current = provider.list_location_criteria(account, campaign.external_campaign_id)
                to_remove = [c['resource_name'] for c in current if c['geo_target_constant'] in remove_geo_ids]
                provider.remove_location_criteria(account, to_remove)
            if add_cities:
                provider.add_location_targeting(account, campaign_resource_name, ', '.join(add_cities))

            current_cities = [c.strip() for c in campaign.region.split(',') if c.strip()]
            final_cities = [c for c in current_cities if c not in (remove_cities or [])]
            final_cities += [c for c in (add_cities or []) if c not in final_cities]
            campaign.region = ', '.join(final_cities)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_geo_targeting failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['region', 'error_message'])
        if campaign.region != before_region:
            self._log_decision(
                campaign, 'update_geo_targeting', {'region': before_region}, {'region': campaign.region},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by,
                approval_status=approval_status, metrics_snapshot=snapshot,
            )
        return campaign

    def add_negative_keywords(self, organization, campaign_id: int, keywords: list[str], *,
                               reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        campaign_resource_name = f'customers/{campaign.advertising_account.customer_id}/campaigns/{campaign.external_campaign_id}'
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            self._provider(campaign.provider).add_negative_keywords(campaign.advertising_account, campaign_resource_name, keywords)
            campaign.error_message = ''
            campaign.save(update_fields=['error_message'])
            self._log_decision(
                campaign, 'add_negative_keywords', {}, {'negative_keywords_added': keywords},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
            )
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.add_negative_keywords failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
        return campaign

    def add_keywords(self, organization, campaign_id: int, ad_group_name: str, keywords: list, *,
                      reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        ad_groups = provider.list_ad_groups(account, campaign.external_campaign_id)
        matches = [ag for ag in ad_groups if ad_group_name.lower() in ag['name'].lower()]
        if not matches:
            campaign.error_message = f'Nenhum ad group encontrado com "{ad_group_name}" no nome.'
            campaign.save(update_fields=['error_message'])
            return campaign
        if len(matches) > 1:
            names = ', '.join(ag['name'] for ag in matches)
            campaign.error_message = f'Mais de um ad group bate com "{ad_group_name}": {names}. Seja mais específico.'
            campaign.save(update_fields=['error_message'])
            return campaign

        snapshot = MetricsService().build_snapshot(campaign)
        keyword_specs = self._keyword_specs(keywords)
        try:
            provider.add_keywords(account, matches[0]['resource_name'], keyword_specs)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.add_keywords failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'add_keywords', {},
            {
                'ad_group': matches[0]['name'], 'ad_group_id': self._resource_id(matches[0]['resource_name']),
                'keywords_added': [kw.text for kw in keyword_specs],
            },
            reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def set_keyword_status(self, organization, campaign_id: int, keyword_text: str, status: str, *,
                            match_type: str | None = None, reason='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        keywords = provider.list_keywords(account, campaign.external_campaign_id)
        matches = [
            kw for kw in keywords
            if kw['text'].lower() == keyword_text.lower() and (match_type is None or kw['match_type'] == match_type)
        ]
        if not matches:
            campaign.error_message = f'Nenhuma keyword "{keyword_text}" encontrada nesta campanha.'
            campaign.save(update_fields=['error_message'])
            return campaign
        if len(matches) > 1:
            details = ', '.join(f"{m['ad_group_name']} ({m['match_type']})" for m in matches)
            campaign.error_message = (
                f'Mais de uma keyword "{keyword_text}" encontrada: {details}. Informe match_type para desambiguar.'
            )
            campaign.save(update_fields=['error_message'])
            return campaign

        keyword = matches[0]
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            provider.set_keyword_status(account, keyword['resource_name'], status)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.set_keyword_status failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        keyword_id = self._resource_id(keyword['resource_name'])
        self._log_decision(
            campaign, 'set_keyword_status',
            {'keyword': keyword_text, 'keyword_id': keyword_id, 'previous_status': keyword['status']},
            {'keyword': keyword_text, 'keyword_id': keyword_id, 'status': status},
            reason=reason, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def create_ad_group(self, organization, campaign_id: int, name: str, *, keywords: list | None = None,
                         ads: list | None = None, cpc_bid: float | None = None,
                         reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        campaign_resource_name = f'customers/{account.customer_id}/campaigns/{campaign.external_campaign_id}'
        snapshot = MetricsService().build_snapshot(campaign)

        keyword_specs = self._keyword_specs(keywords or [])
        ad_specs = [AdContentSpec(headlines=ad['headlines'], descriptions=ad['descriptions']) for ad in (ads or [])]
        if cpc_bid is None:
            # Sem lance explícito, herda o lance do ad group existente mais recente — evita
            # recriar o bug do "1 centavo" (ver set_ad_group_cpc_bids) num grupo novo.
            existing = provider.list_ad_groups(account, campaign.external_campaign_id)
            if existing:
                cpc_bid = existing[0]['cpc_bid_micros'] / 1_000_000

        try:
            ad_group_resource_name = provider.create_ad_group(
                account, campaign_resource_name, campaign.name,
                ad_group_name=name, keywords=keyword_specs, ads=ad_specs,
                landing_url=campaign.landing_url, cpc_bid=cpc_bid,
            )
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.create_ad_group failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'create_ad_group', {},
            {
                'ad_group_name': name, 'ad_group_id': self._resource_id(ad_group_resource_name),
                'keywords': [kw.text for kw in keyword_specs], 'ads_count': len(ad_specs), 'cpc_bid': cpc_bid,
            },
            reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    @staticmethod
    def _validate_asset_lengths(headlines: list[str], descriptions: list[str]) -> None:
        violations = [f'headline {len(h)} chars (máx {HEADLINE_MAX_LEN}): "{h}"' for h in headlines if len(h) > HEADLINE_MAX_LEN]
        violations += [f'description {len(d)} chars (máx {DESCRIPTION_MAX_LEN}): "{d}"' for d in descriptions if len(d) > DESCRIPTION_MAX_LEN]
        if violations:
            raise AssetLengthError('; '.join(violations))

    def add_responsive_search_ad(self, organization, campaign_id: int, ad_group_name: str,
                                  headlines: list[str], descriptions: list[str], *,
                                  reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        self._validate_asset_lengths(headlines, descriptions)

        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        ad_groups = provider.list_ad_groups(account, campaign.external_campaign_id)
        matches = [ag for ag in ad_groups if ad_group_name.lower() in ag['name'].lower()]
        if not matches:
            campaign.error_message = f'Nenhum ad group encontrado com "{ad_group_name}" no nome.'
            campaign.save(update_fields=['error_message'])
            return campaign
        if len(matches) > 1:
            names = ', '.join(ag['name'] for ag in matches)
            campaign.error_message = f'Mais de um ad group bate com "{ad_group_name}": {names}. Seja mais específico.'
            campaign.save(update_fields=['error_message'])
            return campaign

        snapshot = MetricsService().build_snapshot(campaign)
        try:
            provider.create_responsive_search_ad(
                account, matches[0]['resource_name'], campaign.landing_url,
                headlines=headlines, descriptions=descriptions,
            )
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.add_responsive_search_ad failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'add_responsive_search_ad', {},
            {'ad_group': matches[0]['name'], 'ad_group_id': self._resource_id(matches[0]['resource_name']),
             'headlines': headlines, 'descriptions': descriptions},
            reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def set_ad_status(self, organization, campaign_id: int, ad_resource_name: str, status: str, *,
                       reason='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            if status == 'ENABLED':
                # O status do ad group prevalece sobre o do anúncio — um ad group criado PAUSED
                # (ex.: via create_ad_group, que sempre nasce assim) nunca veicula mesmo com o
                # anúncio ENABLED. Bug real observado: ativar só o anúncio e esquecer do grupo
                # deixa tudo parado silenciosamente. Cascateia aqui, como resume_campaign já faz
                # entre campanha/ad group/anúncio.
                ad_group_id = ad_resource_name.split('/adGroupAds/')[-1].split('~')[0]
                ad_group_resource_name = f'customers/{account.customer_id}/adGroups/{ad_group_id}'
                provider.set_ad_group_status(account, ad_group_resource_name, 'ENABLED')
            provider.set_ad_status(account, ad_resource_name, status)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.set_ad_status failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'set_ad_status', {'ad_resource_name': ad_resource_name},
            {'ad_resource_name': ad_resource_name, 'status': status},
            reason=reason, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def update_bidding_strategy(self, organization, campaign_id: int, strategy: str, *, target_cpa: float | None = None,
                                 reason='', hypothesis='', performed_by='user', approval_status='auto_executed') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        account = campaign.advertising_account
        snapshot = MetricsService().build_snapshot(campaign)
        before_strategy = provider.get_bidding_strategy_type(account, campaign.external_campaign_id)
        try:
            provider.update_bidding_strategy(account, campaign.external_campaign_id, strategy, target_cpa=target_cpa)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_bidding_strategy failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'update_bidding_strategy',
            {'bidding_strategy_type': before_strategy},
            {'bidding_strategy_type': strategy, 'target_cpa': target_cpa},
            reason=reason, hypothesis=hypothesis, performed_by=performed_by,
            approval_status=approval_status, metrics_snapshot=snapshot,
        )
        return campaign

    def set_ad_group_cpc_bids(self, organization, campaign_id: int, cpc_bid: float, *,
                               reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        provider = self._provider(campaign.provider)
        snapshot = MetricsService().build_snapshot(campaign)
        before = {}
        try:
            ad_groups = provider.list_ad_groups(campaign.advertising_account, campaign.external_campaign_id)
            for ad_group in ad_groups:
                before[ad_group['name']] = ad_group['cpc_bid_micros'] / 1_000_000
                provider.set_ad_group_cpc_bid(campaign.advertising_account, ad_group['resource_name'], cpc_bid)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.set_ad_group_cpc_bids failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign
        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'set_ad_group_cpc_bids', before, {'cpc_bid': cpc_bid},
            reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def get_search_terms(self, campaign: AdCampaign, days_back: int = 30) -> list[dict]:
        return self._provider(campaign.provider).get_search_terms(
            campaign.advertising_account, campaign.external_campaign_id, days_back,
        )

    def update_ad_content(self, organization, campaign_id: int, headlines: list[str], descriptions: list[str], *,
                           reason='', hypothesis='', performed_by='user') -> AdCampaign:
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        before = {'ad_headlines': campaign.ad_headlines, 'ad_descriptions': campaign.ad_descriptions}
        snapshot = MetricsService().build_snapshot(campaign)
        provider = self._provider(campaign.provider)
        try:
            ad_resource_name = provider.get_primary_ad_resource_name(campaign.advertising_account, campaign.external_campaign_id)
            if not ad_resource_name and settings.GOOGLE_ADS_ENABLED and not settings.GOOGLE_ADS_DRY_RUN:
                raise GoogleAdsProviderError('Nenhum anúncio encontrado nesta campanha para atualizar.', code='ad_not_found')
            provider.update_ad_content(campaign.advertising_account, ad_resource_name or '', headlines, descriptions)
            campaign.ad_headlines = headlines
            campaign.ad_descriptions = descriptions
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_ad_content failed')
            campaign.error_message = exc.user_message
        campaign.save(update_fields=['ad_headlines', 'ad_descriptions', 'error_message'])
        if campaign.ad_headlines != before['ad_headlines'] or campaign.ad_descriptions != before['ad_descriptions']:
            self._log_decision(
                campaign, 'update_ad_content', before,
                {'ad_headlines': campaign.ad_headlines, 'ad_descriptions': campaign.ad_descriptions},
                reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
            )
        return campaign

    def update_ad_content_by_resource(self, organization, campaign_id: int, ad_resource_name: str,
                                       headlines: list[str], descriptions: list[str], *,
                                       reason='', hypothesis='', performed_by='user') -> AdCampaign:
        """Como update_ad_content, mas edita um anúncio ESPECÍFICO (por resource name) em vez de
        'o anúncio principal' — necessário numa campanha com múltiplos ad groups/anúncios, onde
        'o principal' é ambíguo. Não mexe nos campos agregados (ad_headlines/ad_descriptions),
        que continuam representando só um resumo legado de todos os anúncios."""
        campaign = AdCampaign.objects.get(organization=organization, id=campaign_id)
        self._validate_asset_lengths(headlines, descriptions)
        provider = self._provider(campaign.provider)
        snapshot = MetricsService().build_snapshot(campaign)
        try:
            provider.update_ad_content(campaign.advertising_account, ad_resource_name, headlines, descriptions)
            campaign.error_message = ''
        except GoogleAdsProviderError as exc:
            logger.exception('CampaignService.update_ad_content_by_resource failed')
            campaign.error_message = exc.user_message
            campaign.save(update_fields=['error_message'])
            return campaign

        campaign.save(update_fields=['error_message'])
        self._log_decision(
            campaign, 'update_ad_content_by_resource',
            {'ad_resource_name': ad_resource_name},
            {'ad_resource_name': ad_resource_name, 'headlines': headlines, 'descriptions': descriptions},
            reason=reason, hypothesis=hypothesis, performed_by=performed_by, metrics_snapshot=snapshot,
        )
        return campaign

    def get_campaign_diagnostics(self, campaign: AdCampaign) -> dict:
        return self._provider(campaign.provider).get_campaign_diagnostics(
            campaign.advertising_account, campaign.external_campaign_id,
        )
