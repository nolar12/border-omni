from django.contrib import admin
from .models import Organization, UserProfile, Plan, Subscription

admin.site.register(Organization)
admin.site.register(UserProfile)
admin.site.register(Plan)
admin.site.register(Subscription)
