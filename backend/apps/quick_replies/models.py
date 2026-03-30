from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Organization


class QuickReplyCategory(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='quick_reply_categories'
    )
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quick_reply_categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class QuickReply(models.Model):
    # Legacy enum categories kept for backward compat
    CATEGORY_CHOICES = [
        ('GREETING', 'Saudação'),
        ('PRICING', 'Preço'),
        ('AVAILABILITY', 'Disponibilidade'),
        ('SCHEDULING', 'Agendamento'),
        ('INFO', 'Informações'),
        ('CLOSING', 'Encerramento'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='quick_replies'
    )
    # nullable → personal reply; null → shared tenant reply
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='personal_quick_replies'
    )
    # FK to structured category (new model)
    category_ref = models.ForeignKey(
        QuickReplyCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='replies'
    )
    # Legacy category slug (kept for existing records)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='INFO', blank=True
    )
    title = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField(blank=True, default='')
    # Legacy text/shortcut kept for existing records
    text = models.TextField(blank=True, default='')
    shortcut = models.CharField(max_length=50, blank=True, default='')
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quick_replies'
        ordering = ['sort_order', 'title', 'shortcut']

    def __str__(self):
        label = self.title or self.shortcut or '—'
        content = (self.body or self.text)[:40]
        return f"{label} — {content}"
