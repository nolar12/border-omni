import uuid
from django.db import models
from apps.core.models import Organization
from .encrypted_fields import EncryptedTextField, EncryptedCharField

QUALITY_RATING_CHOICES = [
    ('GREEN',   'Alta'),
    ('YELLOW',  'Média'),
    ('RED',     'Baixa'),
    ('UNKNOWN', 'Desconhecido'),
]


class ChannelProvider(models.Model):
    PROVIDER_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('messenger', 'Messenger'),
    ]
    VERIFICATION_CHOICES = [
        ('verified', 'Verified'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        related_name='channel_providers', null=True, blank=True
    )
    name = models.CharField(max_length=100, blank=True, default='')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='whatsapp')
    app_id = models.CharField(max_length=200, blank=True, default='')
    app_secret = EncryptedCharField(max_length=500, blank=True, default='')
    access_token = EncryptedTextField(blank=True, default='')
    phone_number_id = models.CharField(max_length=200, blank=True, default='')
    business_account_id = models.CharField(max_length=200, blank=True, default='')
    instagram_account_id = models.CharField(max_length=200, blank=True, default='')
    page_id = models.CharField(max_length=200, blank=True, default='')
    webhook_verify_token = models.CharField(max_length=200, blank=True, default='')
    webhook_url = models.CharField(max_length=500, blank=True, default='')
    quality_rating = models.CharField(max_length=20, blank=True, default='')
    quality_synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_simulated = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default='pending'
    )
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'channels_channelprovider'

    def __str__(self):
        return f"{self.provider} — {self.phone_number_id or self.instagram_account_id or 'unconfigured'}"


class QualityRatingEvent(models.Model):
    """Histórico de mudanças de quality_rating por canal WhatsApp."""
    channel = models.ForeignKey(
        ChannelProvider, on_delete=models.CASCADE, related_name='quality_events'
    )
    previous_rating = models.CharField(max_length=20, blank=True, default='')
    new_rating = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'channels_qualityratingevent'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.channel} {self.previous_rating}→{self.new_rating}"

    @property
    def is_degradation(self):
        order = {'GREEN': 0, 'YELLOW': 1, 'RED': 2, 'UNKNOWN': 3}
        return order.get(self.new_rating, 3) > order.get(self.previous_rating, 0)


class MetaConversionEvent(models.Model):
    """Registro de cada evento enviado à Meta Conversions API (CAPI)."""
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sent', 'Enviado'),
        ('error', 'Erro'),
        ('skipped', 'Ignorado'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='meta_conversion_events'
    )
    lead = models.ForeignKey(
        'leads.Lead', on_delete=models.CASCADE, related_name='meta_events'
    )
    event_name = models.CharField(max_length=50)
    lead_status = models.CharField(max_length=20, blank=True, default='')
    event_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    phone_hash = models.CharField(max_length=64, blank=True, default='')
    campaign_id = models.CharField(max_length=100, blank=True, default='')
    adset_id = models.CharField(max_length=100, blank=True, default='')
    ad_id = models.CharField(max_length=100, blank=True, default='')
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='BRL')
    payload = models.JSONField(default=dict)
    response = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'meta_conversion_events'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_name} — lead {self.lead_id} [{self.status}]"
