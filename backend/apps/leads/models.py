from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Organization


class LeadTag(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='lead_tags')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='#6B7280', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'lead_tags'
        unique_together = ('organization', 'name')

    def __str__(self):
        return self.name


class Lead(models.Model):
    HOUSING_CHOICES = [
        ('HOUSE_Y', 'Casa com pátio'),
        ('HOUSE_N', 'Casa sem pátio'),
        ('HOUSE',   'Casa'),
        ('APT',     'Apartamento'),
        ('OTHER',   'Outro'),
    ]
    CLASSIFICATION_CHOICES = [
        ('HOT_LEAD',  'Hot Lead'),
        ('WARM_LEAD', 'Warm Lead'),
        ('COLD_LEAD', 'Cold Lead'),
    ]
    EXPERIENCE_CHOICES = [
        ('FIRST_DOG', 'Primeiro cão'),
        ('HAD_DOGS', 'Já teve cães'),
        ('HAD_HIGH_ENERGY', 'Já teve raça de alta energia'),
    ]
    BUDGET_CHOICES = [('YES', 'Sim'), ('NO', 'Não'), ('MAYBE', 'Talvez')]
    TIMELINE_CHOICES = [
        ('NOW', 'Agora'),
        ('THIRTY_DAYS', '30 dias'),
        ('SIXTY_PLUS', '60+ dias'),
    ]
    PURPOSE_CHOICES = [
        ('COMPANION', 'Companheiro'),
        ('SPORT', 'Esporte'),
        ('WORK', 'Trabalho'),
    ]
    STATUS_CHOICES = [
        ('NEW', 'Novo'),
        ('QUALIFYING', 'Qualificando'),
        ('QUALIFIED', 'Qualificado'),
        ('HANDOFF', 'Handoff'),
        ('CLOSED', 'Fechado'),
    ]
    SOURCE_CHOICES = [
        ('INSTAGRAM_AD', 'Anúncio Instagram'),
        ('ORGANIC', 'Orgânico'),
        ('OTHER', 'Outro'),
    ]
    TIER_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C')]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leads')
    phone = models.CharField(max_length=30)
    full_name = models.CharField(max_length=200, null=True, blank=True)
    instagram_handle = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=2, null=True, blank=True)
    housing_type = models.CharField(max_length=10, choices=HOUSING_CHOICES, null=True, blank=True)
    daily_time_minutes = models.IntegerField(null=True, blank=True)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, null=True, blank=True)
    budget_ok = models.CharField(max_length=10, choices=BUDGET_CHOICES, null=True, blank=True)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES, null=True, blank=True)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, null=True, blank=True)
    has_kids = models.BooleanField(default=False)
    has_other_pets = models.BooleanField(default=False)
    score = models.IntegerField(default=0)
    tier = models.CharField(max_length=1, choices=TIER_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='OTHER')
    channels_used = models.CharField(max_length=200, default='')
    is_ai_active = models.BooleanField(default=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_leads')
    conversation_state = models.CharField(max_length=50, null=True, blank=True)
    ab_variant = models.CharField(max_length=1, null=True, blank=True)
    lead_classification = models.CharField(max_length=15, choices=CLASSIFICATION_CHOICES, null=True, blank=True)
    tags = models.ManyToManyField(LeadTag, through='LeadTagAssignment', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.full_name or self.phone} ({self.tier or '?'})"


class LeadTagAssignment(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    tag = models.ForeignKey(LeadTag, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lead_tag_assignments'
        unique_together = ('lead', 'tag')


class Note(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notes'
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.lead} by {self.author}"
