from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Organization


class GenericNote(models.Model):
    COLOR_DEFAULT = 'default'
    COLOR_YELLOW  = 'yellow'
    COLOR_GREEN   = 'green'
    COLOR_BLUE    = 'blue'
    COLOR_PINK    = 'pink'
    COLOR_PURPLE  = 'purple'

    COLOR_CHOICES = [
        (COLOR_DEFAULT, 'Padrão'),
        (COLOR_YELLOW,  'Amarelo'),
        (COLOR_GREEN,   'Verde'),
        (COLOR_BLUE,    'Azul'),
        (COLOR_PINK,    'Rosa'),
        (COLOR_PURPLE,  'Roxo'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='generic_notes'
    )
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generic_notes'
    )
    title   = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    color   = models.CharField(max_length=20, choices=COLOR_CHOICES, default=COLOR_DEFAULT)
    is_pinned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'generic_notes'
        ordering = ['-is_pinned', '-updated_at']

    def __str__(self):
        return f"Nota #{self.id} — {self.title}"
