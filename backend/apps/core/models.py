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
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name}"


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
