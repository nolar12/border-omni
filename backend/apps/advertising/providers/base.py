"""
Abstração de provedor de anúncios (Omni Ads).

Primeira abstração desse tipo no projeto — hoje cada integração externa (ex.: Meta,
em apps/channels/meta_client.py) é um módulo de funções soltas, sem interface comum.
Esta ABC existe para que a camada de domínio (services/) não precise conhecer detalhes
de um provedor específico, permitindo adicionar Meta Ads/TikTok Ads no futuro sem
reescrever CampaignService/ConversionService/MetricsService.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class KeywordSpec:
    text: str
    match_type: str = 'BROAD'  # 'EXACT' | 'PHRASE' | 'BROAD'


@dataclass
class AdContentSpec:
    headlines: list[str]
    descriptions: list[str]


@dataclass
class AdGroupSpec:
    name: str
    keywords: list[KeywordSpec]
    ads: list[AdContentSpec] = field(default_factory=list)
    # CPC máximo deste ad group (teto do leilão, não preço fixo). Sem isso, a Google Ads API
    # cria o ad group com o mínimo técnico (1 centavo) — inelegível para competir em qualquer
    # leilão real (bug observado na campanha "SC | Border Collie | Ninhada Atual | Search").
    # Cai para CampaignSpec.default_cpc_bid quando None.
    cpc_bid: float | None = None


@dataclass
class CampaignSpec:
    name: str
    daily_budget: float
    campaign_type: str = 'search'
    objective: str = 'leads'
    region: str = ''
    radius_km: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    landing_url: str = ''
    headlines: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    # Estrutura multi-ad-group (opcional). Quando preenchida, create_campaign cria um ad group por
    # item, cada um com suas próprias keywords/match types e >=1 RSA — em vez do fluxo legado de 1
    # ad group com `keywords`/`headlines`/`descriptions` em Broad Match.
    ad_groups: list[AdGroupSpec] = field(default_factory=list)
    negative_keywords: list[KeywordSpec] = field(default_factory=list)
    # CPC máximo aplicado a cada ad group que não definir o seu próprio `cpc_bid`.
    default_cpc_bid: float | None = None
    # 'PRESENCE' restringe a exibição a quem está/costuma estar nas localidades segmentadas;
    # 'PRESENCE_OR_INTEREST' (padrão histórico do Google) também exibe para quem só demonstra
    # interesse na região sem estar nela.
    geo_target_type: str = 'PRESENCE'


@dataclass
class ProviderCampaign:
    external_id: str
    status: str
    raw: dict = field(default_factory=dict)
    error_message: str = ''


@dataclass
class MetricSnapshot:
    date: date
    impressions: int = 0
    clicks: int = 0
    cost: float = 0
    ctr: float = 0
    average_cpc: float = 0
    conversions: int = 0
    cost_per_conversion: float | None = None


@dataclass
class ConversionSpec:
    conversion_action: str
    gclid: str
    conversion_value: float | None = None
    currency: str = 'BRL'
    event_id: str = ''
    gbraid: str = ''
    wbraid: str = ''
    # Telefone bruto (não hasheado) do lead, se houver — cada provider aplica a
    # normalização/hash exigida pela sua própria especificação (ex.: E.164 + SHA-256
    # para o Google, formato diferente para outros providers no futuro).
    phone: str = ''


@dataclass
class ProviderResult:
    success: bool
    raw: dict = field(default_factory=dict)
    error_message: str = ''


class AdvertisingProvider(ABC):
    """Interface que qualquer provedor de anúncios (Google Ads, e futuramente Meta/TikTok) implementa."""

    @abstractmethod
    def create_campaign(self, account, spec: CampaignSpec) -> ProviderCampaign:
        ...

    @abstractmethod
    def update_campaign(self, account, external_campaign_id: str, spec: CampaignSpec) -> ProviderCampaign:
        ...

    @abstractmethod
    def pause_campaign(self, account, external_campaign_id: str) -> None:
        ...

    @abstractmethod
    def resume_campaign(self, account, external_campaign_id: str) -> None:
        ...

    @abstractmethod
    def get_campaign(self, account, external_campaign_id: str) -> ProviderCampaign:
        ...

    @abstractmethod
    def get_metrics(self, account, external_campaign_id: str, date_from: date, date_to: date) -> list[MetricSnapshot]:
        ...

    @abstractmethod
    def upload_conversion(self, account, conversion: ConversionSpec) -> ProviderResult:
        ...

    @abstractmethod
    def create_conversion_action(self, account, name: str, category: str) -> str:
        """Cria a ação de conversão no provedor e retorna seu identificador/resource name."""
        ...
