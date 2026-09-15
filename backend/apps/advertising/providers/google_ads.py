"""
GoogleAdsProvider — implementação de AdvertisingProvider para a Google Ads API.

Decisão de arquitetura (validada com o usuário): chamadas via REST puro com `requests`,
no mesmo estilo de apps/channels/meta_client.py, em vez da lib oficial `google-ads`
(gRPC) — evita adicionar uma dependência pesada nova ao projeto.

Enquanto settings.GOOGLE_ADS_ENABLED ou settings.GOOGLE_ADS_DRY_RUN não permitirem
chamadas de escrita reais, os métodos de escrita retornam uma resposta simulada
(logada) em vez de chamar a API do Google — isso permite exercitar toda a camada de
domínio (services/views/UI) sem developer token/conta real.
"""
import hashlib
import logging
import re
import uuid
from datetime import date

import requests
from django.conf import settings
from django.utils import timezone as django_timezone

from .base import (
    AdvertisingProvider, CampaignSpec, ProviderCampaign, MetricSnapshot,
    ConversionSpec, ProviderResult,
)

logger = logging.getLogger('apps')

OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'

# A partir de 15/06/2026 a Google Ads API não aceita mais novos adotantes em
# uploadClickConversions — o caminho recomendado (e único, para quem não já
# tinha esse fluxo funcionando antes do corte) é a Data Manager API, um produto
# separado (lançado em 09/12/2025) com endpoint/host/autenticação próprios:
# sem developer-token, sem login-customer-id no header (vai no corpo, em
# Destination.loginAccount), escopo OAuth próprio (auth/datamanager).
DATA_MANAGER_BASE_URL = 'https://datamanager.googleapis.com/v1'


class GoogleAdsProviderError(Exception):
    """Erro de domínio ao falar com a Google Ads API — nunca deixa o erro bruto subir à view."""

    def __init__(self, user_message: str, *, code: str = 'unknown', raw: dict | None = None):
        self.user_message = user_message
        self.code = code
        self.raw = raw or {}
        super().__init__(user_message)


def _base_url() -> str:
    return f'https://googleads.googleapis.com/{settings.GOOGLE_ADS_API_VERSION}'


def _is_live() -> bool:
    """Só faz chamadas de escrita reais quando ambos os kill-switches permitem."""
    return bool(settings.GOOGLE_ADS_ENABLED) and not settings.GOOGLE_ADS_DRY_RUN


class GoogleAdsProvider(AdvertisingProvider):
    def _get_access_token(self, account) -> str:
        if not account.refresh_token:
            raise GoogleAdsProviderError(
                'Conta Google Ads sem token de acesso configurado. Reconecte a conta.',
                code='missing_refresh_token',
            )
        try:
            resp = requests.post(
                OAUTH_TOKEN_URL,
                data={
                    'client_id': settings.GOOGLE_ADS_CLIENT_ID,
                    'client_secret': settings.GOOGLE_ADS_CLIENT_SECRET,
                    'refresh_token': account.refresh_token,
                    'grant_type': 'refresh_token',
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            raise GoogleAdsProviderError('Não foi possível conectar ao Google agora.', code='network_error') from exc

        if resp.status_code != 200:
            logger.error(f'GoogleAdsProvider token refresh failed: {resp.status_code} {resp.text}')
            raise GoogleAdsProviderError(
                'Sessão do Google Ads expirou. Reconecte a conta.', code='token_expired', raw=resp.json() if resp.content else {}
            )
        return resp.json()['access_token']

    def _headers(self, account) -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token(account)}',
            'developer-token': settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            'login-customer-id': account.login_customer_id or account.customer_id,
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, account, path: str, **kwargs) -> dict:
        url = f'{_base_url()}/{path}'
        try:
            resp = requests.request(method, url, headers=self._headers(account), timeout=30, **kwargs)
        except requests.RequestException as exc:
            logger.exception('GoogleAdsProvider request failed')
            raise GoogleAdsProviderError('Erro de comunicação com a Google Ads API.', code='network_error') from exc

        if resp.status_code >= 400:
            logger.error(f'GoogleAdsProvider API error: {resp.status_code} {resp.text}')
            raise GoogleAdsProviderError(
                self._friendly_error(resp), code=f'http_{resp.status_code}', raw=self._safe_json(resp)
            )
        return self._safe_json(resp)

    def _data_manager_headers(self, account) -> dict:
        # Data Manager API não usa developer-token nem login-customer-id no
        # header — a conta de login/operação vai no corpo de cada Destination.
        return {
            'Authorization': f'Bearer {self._get_access_token(account)}',
            'Content-Type': 'application/json',
        }

    def _data_manager_request(self, method: str, account, path: str, **kwargs) -> dict:
        url = f'{DATA_MANAGER_BASE_URL}/{path}'
        try:
            resp = requests.request(method, url, headers=self._data_manager_headers(account), timeout=30, **kwargs)
        except requests.RequestException as exc:
            logger.exception('GoogleAdsProvider Data Manager request failed')
            raise GoogleAdsProviderError('Erro de comunicação com a Data Manager API.', code='network_error') from exc

        if resp.status_code >= 400:
            logger.error(f'GoogleAdsProvider Data Manager API error: {resp.status_code} {resp.text}')
            raise GoogleAdsProviderError(
                self._friendly_error(resp), code=f'http_{resp.status_code}', raw=self._safe_json(resp)
            )
        return self._safe_json(resp)

    @staticmethod
    def _safe_json(resp) -> dict:
        try:
            return resp.json()
        except ValueError:
            return {}

    @staticmethod
    def _friendly_error(resp) -> str:
        data = GoogleAdsProvider._safe_json(resp)
        error_obj = data.get('error', {}) or {}
        details = error_obj.get('details', []) or []
        for detail in details:
            for err in detail.get('errors', []) or []:
                message = err.get('message')
                if message:
                    return message
        # Formato padrão de erro de API do Google (usado pela Data Manager API,
        # entre outras) — {"error": {"message": "...", "status": "..."}}.
        if error_obj.get('message'):
            if error_obj.get('status') == 'PERMISSION_DENIED' and 'scope' in error_obj['message'].lower():
                return (
                    'A conexão com o Google Ads não tem a permissão (escopo) necessária para esta operação. '
                    'Reconecte a conta em Configurações.'
                )
            return error_obj['message']
        if resp.status_code == 401:
            return 'Autenticação com o Google Ads expirou.'
        if resp.status_code == 403:
            return 'Sem permissão para esta operação na conta Google Ads.'
        if resp.status_code == 429:
            return 'Limite de requisições da Google Ads API atingido. Tente novamente em instantes.'
        return 'A Google Ads API recusou a operação.'

    # ── Escrita ──────────────────────────────────────────────────────────────

    def create_campaign(self, account, spec: CampaignSpec) -> ProviderCampaign:
        if not _is_live():
            fake_id = f'dryrun-{uuid.uuid4().hex[:10]}'
            logger.info(f'[GOOGLE_ADS_DRY_RUN] create_campaign account={account.customer_id} spec={spec}')
            return ProviderCampaign(external_id=fake_id, status='active', raw={'dry_run': True})

        # A Google Ads API exige que o orçamento (CampaignBudget) seja um recurso
        # próprio, criado antes — não pode ser embutido inline na campanha.
        budget_data = self._request(
            'POST', account, f'customers/{account.customer_id}/campaignBudgets:mutate',
            json={'operations': [{'create': {
                'name': f'{spec.name} — Orçamento {uuid.uuid4().hex[:6]}',
                'amountMicros': int(spec.daily_budget * 1_000_000),
                'deliveryMethod': 'STANDARD',
            }}]},
        )
        budget_resource_name = (budget_data.get('results') or [{}])[0].get('resourceName')
        if not budget_resource_name:
            raise GoogleAdsProviderError('Falha ao criar orçamento da campanha.', code='budget_creation_failed', raw=budget_data)

        data = self._request(
            'POST', account, f'customers/{account.customer_id}/campaigns:mutate',
            json=self._build_campaign_payload(spec, budget_resource_name),
        )
        result = (data.get('results') or [{}])[0]
        campaign_resource_name = result.get('resourceName') or ''
        external_id = campaign_resource_name.split('/')[-1] or ''

        # Grupo de anúncios + palavras-chave + anúncio + segmentação geográfica ficam
        # melhor esforço: se algo falhar aqui, a campanha (já criada de verdade no
        # Google) não é perdida — só volta com um aviso, para completar manualmente.
        warnings = []
        try:
            ad_group_resource_name = self._create_ad_group(account, campaign_resource_name, spec)
            if spec.keywords:
                self._add_keywords(account, ad_group_resource_name, spec.keywords)
            if spec.headlines and spec.descriptions:
                self._create_responsive_search_ad(account, ad_group_resource_name, spec)
        except GoogleAdsProviderError as exc:
            logger.exception('GoogleAdsProvider: falha ao configurar grupo de anúncios/palavras-chave/anúncio')
            warnings.append(f'anúncio: {exc.user_message}')

        if spec.region:
            try:
                self._add_location_targeting(account, campaign_resource_name, spec.region)
            except GoogleAdsProviderError as exc:
                logger.exception('GoogleAdsProvider: falha ao configurar segmentação geográfica')
                warnings.append(f'região: {exc.user_message}')

        content_error = f'Campanha criada, mas houve um problema — {"; ".join(warnings)}' if warnings else ''
        return ProviderCampaign(external_id=external_id, status='active', raw=data, error_message=content_error)

    def suggest_geo_target_constants(self, account, location_names: list[str], country_code: str = 'BR', locale: str = 'pt-BR') -> list[str]:
        """
        Resolve nomes de cidade/região em resource names de GeoTargetConstant
        (serviço global, não por customer). A Google retorna várias sugestões por
        termo buscado (a própria cidade, bairros, CEPs, cidades homônimas em outros
        estados) — pega só a melhor (tipo "City", a primeira da lista) por termo,
        para não acabar segmentando bairros/CEPs irrelevantes junto.
        """
        if not location_names:
            return []
        data = self._request(
            'POST', account, 'geoTargetConstants:suggest',
            json={
                'locale': locale,
                'countryCode': country_code,
                'locationNames': {'names': location_names[:25]},
            },
        )
        best_by_term: dict[str, dict] = {}
        for suggestion in data.get('geoTargetConstantSuggestions', []):
            term = suggestion.get('searchTerm', '')
            gtc = suggestion.get('geoTargetConstant', {})
            current_best = best_by_term.get(term)
            # Prioriza o tipo "City"; entre iguais, mantém o primeiro (mais relevante).
            if current_best is None or (gtc.get('targetType') == 'City' and current_best.get('targetType') != 'City'):
                best_by_term[term] = gtc

        return [gtc['resourceName'] for gtc in best_by_term.values() if gtc.get('resourceName')]

    def _add_location_targeting(self, account, campaign_resource_name: str, region: str) -> None:
        """Segmentação geográfica de verdade (restritiva) — a campanha só é elegível a
        aparecer para buscas originadas nas localidades informadas em `region`
        (nomes separados por vírgula, ex.: "Camboriú, Balneário Camboriú")."""
        location_names = [n.strip() for n in region.split(',') if n.strip()]
        if not location_names:
            return

        geo_resource_names = self.suggest_geo_target_constants(account, location_names)
        if not geo_resource_names:
            raise GoogleAdsProviderError(
                f'Nenhuma localização encontrada para "{region}".', code='geo_target_not_found',
            )

        operations = [{'create': {
            'campaign': campaign_resource_name,
            'location': {'geoTargetConstant': resource_name},
        }} for resource_name in geo_resource_names]
        self._request(
            'POST', account, f'customers/{account.customer_id}/campaignCriteria:mutate',
            json={'operations': operations},
        )

    def _create_ad_group(self, account, campaign_resource_name: str, spec: CampaignSpec) -> str:
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/adGroups:mutate',
            json={'operations': [{'create': {
                'name': f'{spec.name} — Grupo 1',
                'campaign': campaign_resource_name,
                'status': 'PAUSED',
                'type': 'SEARCH_STANDARD',
            }}]},
        )
        resource_name = (data.get('results') or [{}])[0].get('resourceName')
        if not resource_name:
            raise GoogleAdsProviderError('Falha ao criar grupo de anúncios.', code='ad_group_creation_failed', raw=data)
        return resource_name

    def _add_keywords(self, account, ad_group_resource_name: str, keywords: list[str]) -> None:
        operations = [{'create': {
            'adGroup': ad_group_resource_name,
            'status': 'ENABLED',
            'keyword': {'text': kw, 'matchType': 'BROAD'},
        }} for kw in keywords]
        self._request(
            'POST', account, f'customers/{account.customer_id}/adGroupCriteria:mutate',
            json={'operations': operations, 'partialFailure': True},
        )

    def _create_responsive_search_ad(self, account, ad_group_resource_name: str, spec: CampaignSpec) -> None:
        self._request(
            'POST', account, f'customers/{account.customer_id}/adGroupAds:mutate',
            json={'operations': [{'create': {
                'adGroup': ad_group_resource_name,
                'status': 'PAUSED',
                'ad': {
                    'finalUrls': [spec.landing_url] if spec.landing_url else [],
                    'responsiveSearchAd': {
                        'headlines': [{'text': h} for h in spec.headlines[:15]],
                        'descriptions': [{'text': d} for d in spec.descriptions[:4]],
                    },
                },
            }}]},
        )

    def get_search_terms(self, account, external_campaign_id: str, days_back: int = 30) -> list[dict]:
        """Termos de busca reais que dispararam o anúncio — base para negativação e novas keywords."""
        if not _is_live():
            return []
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': (
                'SELECT search_term_view.search_term, segments.keyword.info.text, '
                'segments.keyword.info.match_type, metrics.clicks, metrics.cost_micros, '
                'metrics.conversions, metrics.impressions '
                f'FROM search_term_view WHERE campaign.id = {external_campaign_id} '
                f'AND segments.date DURING LAST_{days_back}_DAYS '
                'ORDER BY metrics.cost_micros DESC LIMIT 100'
            )},
        )
        results = []
        for row in data.get('results') or []:
            metrics = row.get('metrics', {})
            segments = row.get('segments', {})
            results.append({
                'search_term': row.get('searchTermView', {}).get('searchTerm', ''),
                'matched_keyword': segments.get('keyword', {}).get('info', {}).get('text', ''),
                'match_type': segments.get('keyword', {}).get('info', {}).get('matchType', ''),
                'impressions': int(metrics.get('impressions', 0)),
                'clicks': int(metrics.get('clicks', 0)),
                'cost': int(metrics.get('costMicros', 0)) / 1_000_000,
                'conversions': float(metrics.get('conversions', 0)),
            })
        return results

    def add_negative_keywords(self, account, campaign_resource_name: str, keywords: list[str], match_type: str = 'PHRASE') -> None:
        """Negativas a nível de campanha — bloqueiam a busca inteira nessa campanha."""
        if not keywords:
            return
        if not _is_live():
            logger.info(f'[GOOGLE_ADS_DRY_RUN] add_negative_keywords campaign={campaign_resource_name} keywords={keywords}')
            return
        operations = [{'create': {
            'campaign': campaign_resource_name,
            'negative': True,
            'keyword': {'text': kw, 'matchType': match_type},
        }} for kw in keywords]
        self._request(
            'POST', account, f'customers/{account.customer_id}/campaignCriteria:mutate',
            json={'operations': operations, 'partialFailure': True},
        )

    def update_campaign(self, account, external_campaign_id: str, spec: CampaignSpec) -> ProviderCampaign:
        """Hoje só atualiza o orçamento diário. O orçamento é um recurso próprio
        (CampaignBudget) — não dá para mudar o valor direto no recurso da campanha,
        é preciso descobrir qual orçamento ela usa e atualizar esse recurso."""
        if not _is_live():
            logger.info(f'[GOOGLE_ADS_DRY_RUN] update_campaign id={external_campaign_id} spec={spec}')
            return ProviderCampaign(external_id=external_campaign_id, status='active', raw={'dry_run': True})

        lookup = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': f'SELECT campaign.campaign_budget FROM campaign WHERE campaign.id = {external_campaign_id}'},
        )
        rows = lookup.get('results') or []
        budget_resource_name = rows[0]['campaign']['campaignBudget'] if rows else None
        if not budget_resource_name:
            raise GoogleAdsProviderError('Campanha ou orçamento não encontrado.', code='budget_not_found', raw=lookup)

        data = self._request(
            'POST', account, f'customers/{account.customer_id}/campaignBudgets:mutate',
            json={'operations': [{'update': {
                'resourceName': budget_resource_name,
                'amountMicros': int(spec.daily_budget * 1_000_000),
            }, 'updateMask': 'amountMicros'}]},
        )
        return ProviderCampaign(external_id=external_campaign_id, status='active', raw=data)

    def pause_campaign(self, account, external_campaign_id: str) -> None:
        self._set_campaign_status(account, external_campaign_id, 'PAUSED')

    def resume_campaign(self, account, external_campaign_id: str) -> None:
        """
        Reativar a campanha sozinha NÃO basta: toda campanha/anúncio criado por
        este sistema nasce PAUSED em todos os 3 níveis (campanha, grupo de
        anúncios e o próprio anúncio) como proteção contra ativação acidental
        (ver _build_campaign_payload/_create_ad_group/_create_responsive_search_ad).
        Sem reativar também o grupo e o anúncio, a campanha fica com status
        ENABLED mas o Google Ads mostra "Not eligible — all ad groups/ads are
        paused" e nada é veiculado de fato.
        """
        self._set_campaign_status(account, external_campaign_id, 'ENABLED')
        if not _is_live():
            logger.info(f'[GOOGLE_ADS_DRY_RUN] resume ad groups/ads id={external_campaign_id}')
            return
        self._enable_paused_ad_groups(account, external_campaign_id)
        self._enable_paused_ads(account, external_campaign_id)

    def _set_campaign_status(self, account, external_campaign_id: str, status: str) -> None:
        if not _is_live():
            logger.info(f'[GOOGLE_ADS_DRY_RUN] set_campaign_status id={external_campaign_id} status={status}')
            return
        self._request(
            'POST', account, f'customers/{account.customer_id}/campaigns:mutate',
            json={'operations': [{'update': {
                'resourceName': f'customers/{account.customer_id}/campaigns/{external_campaign_id}',
                'status': status,
            }, 'updateMask': 'status'}]},
        )

    def _enable_paused_ad_groups(self, account, external_campaign_id: str) -> None:
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': (
                'SELECT ad_group.resource_name FROM ad_group '
                f'WHERE campaign.id = {external_campaign_id} AND ad_group.status = PAUSED'
            )},
        )
        resource_names = [row['adGroup']['resourceName'] for row in data.get('results') or []]
        if not resource_names:
            return
        operations = [{'update': {
            'resourceName': rn, 'status': 'ENABLED',
        }, 'updateMask': 'status'} for rn in resource_names]
        self._request(
            'POST', account, f'customers/{account.customer_id}/adGroups:mutate',
            json={'operations': operations, 'partialFailure': True},
        )

    def _enable_paused_ads(self, account, external_campaign_id: str) -> None:
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': (
                'SELECT ad_group_ad.resource_name FROM ad_group_ad '
                f'WHERE campaign.id = {external_campaign_id} AND ad_group_ad.status = PAUSED'
            )},
        )
        resource_names = [row['adGroupAd']['resourceName'] for row in data.get('results') or []]
        if not resource_names:
            return
        operations = [{'update': {
            'resourceName': rn, 'status': 'ENABLED',
        }, 'updateMask': 'status'} for rn in resource_names]
        self._request(
            'POST', account, f'customers/{account.customer_id}/adGroupAds:mutate',
            json={'operations': operations, 'partialFailure': True},
        )

    # ── Leitura ──────────────────────────────────────────────────────────────

    def get_campaign(self, account, external_campaign_id: str) -> ProviderCampaign:
        if not _is_live():
            return ProviderCampaign(external_id=external_campaign_id, status='active', raw={'dry_run': True})
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': (
                'SELECT campaign.id, campaign.status FROM campaign '
                f'WHERE campaign.id = {external_campaign_id}'
            )},
        )
        rows = data.get('results') or []
        status = rows[0]['campaign']['status'] if rows else 'UNKNOWN'
        return ProviderCampaign(external_id=external_campaign_id, status=status, raw=data)

    def get_metrics(self, account, external_campaign_id: str, date_from: date, date_to: date) -> list[MetricSnapshot]:
        if not _is_live():
            return []
        data = self._request(
            'POST', account, f'customers/{account.customer_id}/googleAds:search',
            json={'query': (
                'SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, '
                'metrics.ctr, metrics.average_cpc, metrics.conversions, metrics.cost_per_conversion '
                f'FROM campaign WHERE campaign.id = {external_campaign_id} '
                f"AND segments.date BETWEEN '{date_from.isoformat()}' AND '{date_to.isoformat()}'"
            )},
        )
        snapshots = []
        for row in data.get('results') or []:
            metrics = row.get('metrics', {})
            segments = row.get('segments', {})
            snapshots.append(MetricSnapshot(
                date=date.fromisoformat(segments.get('date')),
                impressions=int(metrics.get('impressions', 0)),
                clicks=int(metrics.get('clicks', 0)),
                cost=int(metrics.get('costMicros', 0)) / 1_000_000,
                ctr=float(metrics.get('ctr', 0)),
                average_cpc=int(metrics.get('averageCpc', 0)) / 1_000_000,
                conversions=int(float(metrics.get('conversions', 0))),
                cost_per_conversion=(
                    int(metrics.get('costPerConversion', 0)) / 1_000_000
                    if metrics.get('costPerConversion') else None
                ),
            ))
        return snapshots

    @staticmethod
    def _normalize_phone_e164(phone: str) -> str:
        """E.164: '+' seguido só de dígitos, com DDI do Brasil quando ausente —
        exigido pela Data Manager API antes do hash (diferente da normalização
        sem '+' usada pela Meta Conversions API)."""
        digits = re.sub(r'\D', '', phone or '')
        if not digits:
            return ''
        if not digits.startswith('55'):
            digits = '55' + digits
        return f'+{digits}'

    @staticmethod
    def _sha256_hex(value: str) -> str:
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def upload_conversion(self, account, conversion: ConversionSpec) -> ProviderResult:
        """
        Envia o evento de conversão via Data Manager API (events:ingest) — a
        Google Ads API uploadClickConversions está descontinuada para novos
        adotantes desde 15/06/2026 e este projeto nunca teve upload funcionando
        antes desse corte, então não há acesso legado a preservar.

        productDestinationId precisa ser o ID NUMÉRICO da conversion action
        (não o resource name) — ver conversion.conversion_action, que chega como
        "customers/{id}/conversionActions/{numeric_id}".
        """
        if not _is_live():
            logger.info(f'[GOOGLE_ADS_DRY_RUN] upload_conversion account={account.customer_id} conversion={conversion}')
            return ProviderResult(success=True, raw={'dry_run': True})

        ad_identifiers = {}
        if conversion.gclid:
            ad_identifiers['gclid'] = conversion.gclid
        elif conversion.gbraid:
            ad_identifiers['gbraid'] = conversion.gbraid
        elif conversion.wbraid:
            ad_identifiers['wbraid'] = conversion.wbraid
        if not ad_identifiers:
            return ProviderResult(success=False, error_message='Nenhum identificador de clique (gclid/gbraid/wbraid) disponível.')

        numeric_conversion_action_id = conversion.conversion_action.rstrip('/').split('/')[-1]

        destination = {
            'operatingAccount': {'accountType': 'GOOGLE_ADS', 'accountId': account.customer_id},
            'productDestinationId': numeric_conversion_action_id,
        }
        if account.login_customer_id and account.login_customer_id != account.customer_id:
            destination['loginAccount'] = {'accountType': 'GOOGLE_ADS', 'accountId': account.login_customer_id}

        event = {
            'adIdentifiers': ad_identifiers,
            'currency': conversion.currency,
            'eventTimestamp': django_timezone.now().isoformat(),
            'transactionId': conversion.event_id,
            'eventSource': 'WEB',
        }
        if conversion.conversion_value is not None:
            event['conversionValue'] = conversion.conversion_value

        payload = {'destinations': [destination], 'events': [event]}

        # Dado pessoal (telefone) só entra hasheado (SHA-256, após normalização
        # E.164) — nunca em texto puro, conforme a especificação da Data Manager API.
        if conversion.phone:
            normalized = self._normalize_phone_e164(conversion.phone)
            if normalized:
                event['userData'] = {'userIdentifiers': [{'phoneNumber': self._sha256_hex(normalized)}]}
                payload['encoding'] = 'HEX'

        try:
            data = self._data_manager_request('POST', account, 'events:ingest', json=payload)
            return ProviderResult(success=True, raw=data)
        except GoogleAdsProviderError as exc:
            return ProviderResult(success=False, raw=exc.raw, error_message=exc.user_message)

    def create_conversion_action(self, account, name: str, category: str) -> str:
        """
        Cria uma Conversion Action (tipo UPLOAD_CLICKS, por gclid) no Google Ads.
        Necessária antes de qualquer envio via upload_conversion — sem ela o
        Google recusa o upload. `category` é um dos valores do enum
        ConversionActionCategory (ex.: 'QUALIFIED_LEAD', 'LEAD', 'PURCHASE').
        """
        if not _is_live():
            fake_id = f'dryrun-conversion-{uuid.uuid4().hex[:10]}'
            logger.info(f'[GOOGLE_ADS_DRY_RUN] create_conversion_action account={account.customer_id} name={name}')
            return f'customers/{account.customer_id}/conversionActions/{fake_id}'

        data = self._request(
            'POST', account, f'customers/{account.customer_id}/conversionActions:mutate',
            json={'operations': [{'create': {
                'name': name,
                'type': 'UPLOAD_CLICKS',
                'category': category,
                'status': 'ENABLED',
                # alwaysUseDefaultValue=False é essencial para o evento "sale": sem
                # isso, o Google ignoraria o valor real da venda e sempre reportaria 0,
                # inviabilizando o bidding por valor/ROAS na conversão de maior peso.
                'valueSettings': {'defaultValue': 0, 'alwaysUseDefaultValue': False},
            }}]},
        )
        resource_name = (data.get('results') or [{}])[0].get('resourceName')
        if not resource_name:
            raise GoogleAdsProviderError('Falha ao criar ação de conversão.', code='conversion_action_creation_failed', raw=data)
        return resource_name

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_campaign_payload(spec: CampaignSpec, budget_resource_name: str) -> dict:
        """Monta o payload de criação de uma campanha Search simples de geração de leads.

        Nasce sempre PAUSED — nunca é ativada automaticamente pela integração,
        precisa de uma ação explícita (resume) para começar a veicular e gastar.
        """
        return {
            'operations': [{'create': {
                'name': spec.name,
                'advertisingChannelType': 'SEARCH',
                'status': 'PAUSED',
                'campaignBudget': budget_resource_name,
                'manualCpc': {},
                'networkSettings': {
                    'targetGoogleSearch': True,
                    'targetSearchNetwork': True,
                    'targetContentNetwork': False,
                    'targetPartnerSearchNetwork': False,
                },
                # Exigido pela Google (regulação de transparência de anúncios políticos da UE).
                # Um canil vendendo filhotes nunca é publicidade política.
                'containsEuPoliticalAdvertising': 'DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING',
                # ValueTrack — a Google substitui esses placeholders no clique real,
                # permitindo religar o lead ao grupo de anúncios/anúncio/keyword/busca
                # exatos (AdLeadAttribution.ad_group_id/ad_id/keyword/search_term).
                'finalUrlSuffix': (
                    'gclid={gclid}&gbraid={gbraid}&wbraid={wbraid}'
                    '&utm_source=google&utm_medium=cpc&utm_campaign={campaignid}'
                    '&adgroupid={adgroupid}&adid={creative}'
                    '&keyword={keyword}&matchtype={matchtype}&searchterm={searchterm}'
                ),
            }}],
        }


# ── OAuth (fluxo discover/finalize, mesma forma de apps/channels/meta_client.py) ──

def exchange_code_for_tokens(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Troca o authorization code do consentimento Google por access_token + refresh_token."""
    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
        timeout=15,
    )
    if resp.status_code != 200:
        logger.error(f'GoogleAds OAuth code exchange failed: {resp.status_code} {resp.text}')
        raise GoogleAdsProviderError('Falha ao autenticar com o Google.', code='oauth_exchange_failed')
    data = resp.json()
    if not data.get('refresh_token'):
        raise GoogleAdsProviderError(
            'O Google não retornou um refresh_token (tente reconectar com "prompt=consent").',
            code='missing_refresh_token',
        )
    return data


def list_accessible_customers(access_token: str, developer_token: str) -> list[str]:
    """Lista os customer IDs da Google Ads API acessíveis pelo token informado."""
    resp = requests.get(
        f'{_base_url()}/customers:listAccessibleCustomers',
        headers={'Authorization': f'Bearer {access_token}', 'developer-token': developer_token},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.error(f'GoogleAds listAccessibleCustomers failed: {resp.status_code} {resp.text}')
        raise GoogleAdsProviderError('Falha ao listar contas Google Ads acessíveis.', code='list_customers_failed')
    resource_names = resp.json().get('resourceNames', [])
    return [rn.split('/')[-1] for rn in resource_names]
