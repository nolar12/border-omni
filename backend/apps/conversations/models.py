from django.db import models
from apps.leads.models import Lead


class Conversation(models.Model):
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, related_name='conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'

    def __str__(self):
        return f"Conversation with {self.lead}"


class Message(models.Model):
    DIRECTION_CHOICES = [('IN', 'Inbound'), ('OUT', 'Outbound')]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    text = models.TextField()
    provider_message_id = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.direction}: {self.text[:50]}"
