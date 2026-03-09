from django.contrib import admin
from .models import Lead, LeadTag, LeadTagAssignment, Note

admin.site.register(Lead)
admin.site.register(LeadTag)
admin.site.register(Note)
