from django.contrib import admin
from .models import QuickReplyCategory, QuickReply


@admin.register(QuickReplyCategory)
class QuickReplyCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'sort_order', 'created_at']
    list_filter = ['organization']
    ordering = ['organization', 'sort_order', 'name']


@admin.register(QuickReply)
class QuickReplyAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_ref', 'user', 'organization', 'sort_order', 'is_active']
    list_filter = ['organization', 'is_active', 'category_ref']
    search_fields = ['title', 'body', 'shortcut']
    ordering = ['organization', 'sort_order', 'title']
