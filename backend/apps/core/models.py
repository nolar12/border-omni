import uuid
from django.db import models
from django.contrib.auth.models import User


class AgentConfig(models.Model):
    MODEL_CHOICES = [
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
    ]

    organization = models.OneToOneField(
        'Organization', on_delete=models.CASCADE, related_name='agent_config'
    )
    openai_api_key = models.CharField(max_length=255, blank=True)
    model = models.CharField(max_length=50, choices=MODEL_CHOICES, default='gpt-4o-mini')
    system_prompt = models.TextField(blank=True)
    temperature = models.FloatField(default=0.7)
    rag_enabled = models.BooleanField(default=False)
    match_threshold = models.FloatField(default=0.75)
    match_count = models.IntegerField(default=5)
    max_history_messages = models.IntegerField(default=10)
    cordiality_enabled = models.BooleanField(default=False)
    cordiality_use_ai = models.BooleanField(default=False)
    bot_enabled = models.BooleanField(default=True)
    initial_message = models.TextField(blank=True, default='')
    sequence_message = models.TextField(blank=True, default='')
    link_message = models.TextField(blank=True, default='')
    # Template de conversa editável por tenant.
    # Quando vazio, o sistema usa o CONVERSATION_SYSTEM_PROMPT_TEMPLATE hard-coded como fallback.
    conversation_template = models.TextField(blank=True, default='')
    # Quando False, as sugestões são geradas com base exclusivamente no RAG (Supabase).
    # O template só entra como fallback se o RAG não retornar resultados.
    use_conversation_template = models.BooleanField(default=True)
    # Horário de atendimento: quando habilitado, mensagens fora do range recebem off_hours_message.
    # off_hours_start > off_hours_end indica período que cruza a meia-noite (ex: 21:00 → 06:00).
    off_hours_enabled = models.BooleanField(default=False)
    off_hours_start = models.TimeField(null=True, blank=True)
    off_hours_end = models.TimeField(null=True, blank=True)
    off_hours_message = models.TextField(blank=True, default='')
    off_hours_timezone = models.CharField(max_length=60, blank=True, default='America/Sao_Paulo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_configs'

    def __str__(self):
        return f"AgentConfig({self.organization.name})"

    def is_ready(self):
        return bool(self.rag_enabled and self.openai_api_key)


class Organization(models.Model):
    name = models.CharField(max_length=200)
    api_key = models.UUIDField(default=uuid.uuid4, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=50, default='agent', blank=True)
    phone = models.CharField(max_length=30, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name}"


def _media_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower()
    return f'initial_media/org_{instance.agent_config.organization_id}/{uuid.uuid4().hex}{ext}'


class InitialMessageMedia(models.Model):
    MEDIA_TYPE_CHOICES = [('image', 'Imagem'), ('video', 'Vídeo')]

    agent_config = models.ForeignKey(
        AgentConfig, on_delete=models.CASCADE, related_name='initial_media'
    )
    file = models.FileField(upload_to=_media_upload_path)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image')
    original_name = models.CharField(max_length=255, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'initial_message_media'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.media_type} — {self.original_name}'


class GalleryMedia(models.Model):
    MEDIA_TYPE_CHOICES = [('IMAGE', 'Imagem'), ('VIDEO', 'Vídeo'), ('DOCUMENT', 'Documento'), ('AUDIO', 'Áudio')]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='gallery_media'
    )
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    file_url = models.CharField(max_length=2000)
    mime_type = models.CharField(max_length=100, blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='IMAGE')
    size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gallery_media'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} [{self.media_type}]'


PLAN_CHOICES = [
    ('free', 'Free'),
    ('pro', 'Pro'),
    ('enterprise', 'Enterprise'),
]


class Plan(models.Model):
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    max_leads = models.IntegerField(default=100)
    max_agents = models.IntegerField(default=2)
    max_channels = models.IntegerField(default=1)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'plans'

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trial', 'Trial'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'

    def __str__(self):
        return f"{self.organization.name} - {self.plan.name}"
