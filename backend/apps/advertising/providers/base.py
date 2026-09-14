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
