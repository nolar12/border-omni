from django.db import models
from apps.core.models import Organization


class QuickReply(models.Model):
    CATEGORY_CHOICES = [
        ('GREETING', 'Saudação'),
        ('PRICING', 'Preço'),
        ('AVAILABILITY', 'Disponibilidade'),
        ('SCHEDULING', 'Agendamento'),
        ('INFO', 'Informações'),
        ('CLOSING', 'Encerramento'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='quick_replies')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='INFO')
    text = models.TextField()
    shortcut = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quick_replies'

    def __str__(self):
        return f"/{self.shortcut} — {self.text[:40]}"
