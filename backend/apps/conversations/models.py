from django.db import models
from apps.leads.models import Lead
from apps.core.models import Organization
from apps.channels.models import ChannelProvider


class Conversation(models.Model):
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('messenger', 'Messenger'),
        ('other', 'Other'),
    ]
    STATE_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('pending', 'Pending'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='conversations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='whatsapp')
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default='active')
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        unique_together = ('lead', 'channel')

    def __str__(self):
        return f"Conversation with {self.lead} [{self.channel}]"


class Message(models.Model):
    DIRECTION_CHOICES = [('IN', 'Inbound'), ('OUT', 'Outbound')]
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    text = models.TextField()
    provider_message_id = models.CharField(max_length=200, null=True, blank=True)
    msg_status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.direction}: {self.text[:50]}"


class MessageTemplate(models.Model):
    CATEGORY_CHOICES = [
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
        ('AUTHENTICATION', 'Authentication'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Rascunho'),
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAUSED', 'Paused'),
        ('DISABLED', 'Disabled'),
    ]

    HEADER_TYPE_CHOICES = [
        ('NONE', 'Sem cabeçalho'),
        ('TEXT', 'Texto'),
        ('IMAGE', 'Imagem'),
        ('VIDEO', 'Vídeo'),
        ('DOCUMENT', 'Documento'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='message_templates')
    channel = models.ForeignKey(ChannelProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name='message_templates')
    name = models.CharField(max_length=512, help_text='Snake_case, apenas letras minúsculas e underscores')
    language = models.CharField(max_length=10, default='pt_BR')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='UTILITY')
    header_type = models.CharField(max_length=10, choices=HEADER_TYPE_CHOICES, default='NONE')
    header_text = models.TextField(blank=True, help_text='Cabeçalho de texto (somente quando header_type=TEXT)')
    body_text = models.TextField(help_text='Corpo principal. Use {{1}}, {{2}} para variáveis')
    footer_text = models.TextField(blank=True, help_text='Rodapé opcional do template')
    header_media_url = models.URLField(max_length=2000, blank=True, help_text='URL padrão de mídia do cabeçalho (imagem/vídeo/documento). Usada como pré-preenchimento no envio.')
    meta_media_handle = models.TextField(blank=True, help_text='Handle retornado pela Meta após upload de mídia via Resumable Upload API. Usado na submissão do template.')
    meta_template_id = models.CharField(max_length=100, blank=True, help_text='ID retornado pela Meta após aprovação')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_templates'
        unique_together = ('organization', 'name', 'language')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.language}] — {self.status}"
