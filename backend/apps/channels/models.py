from django.db import models
from apps.core.models import Organization


class ChannelProvider(models.Model):
    PROVIDER_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
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
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='whatsapp')
    app_id = models.CharField(max_length=200, blank=True, default='')
    access_token = models.TextField(blank=True, default='')
    phone_number_id = models.CharField(max_length=200, blank=True, default='')
    business_account_id = models.CharField(max_length=200, blank=True, default='')
    instagram_account_id = models.CharField(max_length=200, blank=True, default='')
    page_id = models.CharField(max_length=200, blank=True, default='')
    webhook_verify_token = models.CharField(max_length=200, blank=True, default='')
    webhook_url = models.CharField(max_length=500, blank=True, default='')
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
