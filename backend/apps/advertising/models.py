import uuid
from django.db import models
from apps.core.models import Organization
from apps.channels.encrypted_fields import EncryptedTextField

PROVIDER_CHOICES = [
    ('google_ads', 'Google Ads'),
]


def _generate_click_token() -> str:
    return uuid.uuid4().hex[:8].upper()


class AdvertisingAccount(models.Model):
    """Conexão do tenant com uma conta de anúncios externa (ex.: uma conta Google Ads)."""
    STATUS_CHOICES = [
        ('connected', 'Conectado'),
        ('disconnected', 'Desconectado'),
        ('error', 'Erro'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='advertising_accounts'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='google_ads')
    customer_id = models.CharField(max_length=50, help_text='Google Ads customer ID (sem hífens).')
    login_customer_id = models.CharField(
        max_length=50, blank=True, default='', help_text='Manager Account (MCC) ID, se aplicável.'
    )
    refresh_token = EncryptedTextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='connected')
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'advertising_accounts'
        unique_together = ('organization', 'provider', 'customer_id')

    def __str__(self):
        return f'{self.provider}:{self.customer_id} ({self.organization.name})'


class AdCampaign(models.Model):
    """Campanha de anúncio interna, opcionalmente vinculada a uma ninhada."""
    CAMPAIGN_TYPE_CHOICES = [
        ('search', 'Pesquisa (Search)'),
    ]
    OBJECTIVE_CHOICES = [
        ('leads', 'Geração de contatos'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Rascunho'),
        ('pending', 'Publicando'),
        ('active', 'Ativa'),
        ('paused', 'Pausada'),
        ('error', 'Erro'),
        ('ended', 'Encerrada'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='ad_campaigns'
    )
    advertising_account = models.ForeignKey(
        AdvertisingAccount, on_delete=models.CASCADE, related_name='campaigns'
    )
    litter = models.ForeignKey(
        'kennel.Litter', on_delete=models.SET_NULL, null=True, blank=True, related_name='ad_campaigns'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='google_ads')
    external_campaign_id = models.CharField(max_length=100, blank=True, default='')
    name = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPE_CHOICES, default='search')
    objective = models.CharField(max_length=20, choices=OBJECTIVE_CHOICES, default='leads')
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2)
    total_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    region = models.CharField(max_length=200, blank=True, default='')
    radius_km = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    landing_url = models.URLField(max_length=500, blank=True, default='')
    ad_headlines = models.JSONField(default=list, blank=True)
    ad_descriptions = models.JSONField(default=list, blank=True)
    ad_keywords = models.JSONField(default=list, blank=True)
    client_request_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ad_campaigns'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} [{self.status}]'


class AdMetric(models.Model):
    """Snapshot diário de métricas de uma campanha."""
    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE, related_name='metrics')
    date = models.DateField()
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ctr = models.FloatField(default=0)
    average_cpc = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conversions = models.PositiveIntegerField(default=0)
    cost_per_conversion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ad_metrics'
        unique_together = ('campaign', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.campaign_id} @ {self.date}'


class AdClickToken(models.Model):
    """Token curto emitido quando a landing page captura gclid/UTM, para religar o clique ao Lead."""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='ad_click_tokens'
    )
    token = models.CharField(max_length=16, unique=True, default=_generate_click_token)
    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='click_tokens'
    )
    litter = models.ForeignKey(
        'kennel.Litter', on_delete=models.SET_NULL, null=True, blank=True, related_name='ad_click_tokens'
    )
    gclid = models.CharField(max_length=200, blank=True, default='')
    utm_source = models.CharField(max_length=100, blank=True, default='')
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=150, blank=True, default='')
    utm_content = models.CharField(max_length=150, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ad_click_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return self.token


class AdLeadAttribution(models.Model):
    """Ligação definitiva entre um Lead e a campanha/clique de anúncio que o originou."""
    lead = models.OneToOneField('leads.Lead', on_delete=models.CASCADE, related_name='ad_attribution')
    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='lead_attributions'
    )
    gclid = models.CharField(max_length=200, blank=True, default='')
    utm_source = models.CharField(max_length=100, blank=True, default='')
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=150, blank=True, default='')
    utm_content = models.CharField(max_length=150, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ad_lead_attributions'

    def __str__(self):
        return f'Attribution(lead={self.lead_id}, campaign={self.campaign_id})'


class AdEvent(models.Model):
    """Evento interno do Border Omni relacionado a anúncios (sempre gravado)."""
    EVENT_TYPE_CHOICES = [
        ('page_view', 'Visita à landing'),
        ('whatsapp_click', 'Clique no WhatsApp'),
        ('lead_created', 'Lead criado'),
        ('qualified_lead', 'Lead qualificado'),
        ('reservation', 'Reserva'),
        ('sale', 'Venda'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ad_events')
    lead = models.ForeignKey(
        'leads.Lead', on_delete=models.SET_NULL, null=True, blank=True, related_name='ad_events'
    )
    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ad_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} — lead {self.lead_id}'


class AdConversionUpload(models.Model):
    """Registro de cada conversão efetivamente enviada (ou tentada) ao provedor de anúncios."""
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sent', 'Enviado'),
        ('error', 'Erro'),
        ('skipped', 'Ignorado'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='ad_conversion_uploads'
    )
    ad_event = models.OneToOneField(AdEvent, on_delete=models.CASCADE, related_name='conversion_upload')
    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversion_uploads'
    )
    gclid = models.CharField(max_length=200, blank=True, default='')
    conversion_action = models.CharField(max_length=200, blank=True, default='')
    conversion_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='BRL')
    event_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    payload = models.JSONField(default=dict, blank=True)
    response = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ad_conversion_uploads'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.ad_event.event_type} — {self.status}'


class AdvertisingSettings(models.Model):
    """Configuração de Omni Ads por tenant — inclui o feature flag por cliente."""
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='advertising_settings'
    )
    is_enabled = models.BooleanField(default=False)
    send_qualified_events = models.BooleanField(default=True)
    send_reservation_events = models.BooleanField(default=True)
    send_sale_events = models.BooleanField(default=True)
    default_daily_budget = models.DecimalField(max_digits=10, decimal_places=2, default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'advertising_settings'

    def __str__(self):
        return f'AdvertisingSettings({self.organization.name})'
