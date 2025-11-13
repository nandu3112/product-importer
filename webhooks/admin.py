from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Webhook, WebhookLog

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'event_type', 'is_active', 'created_at']
    list_filter = ['event_type', 'is_active', 'created_at']
    search_fields = ['name', 'url']
    list_editable = ['is_active']

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['webhook', 'event_type', 'is_success', 'response_code', 'duration', 'created_at']
    list_filter = ['is_success', 'event_type', 'created_at']
    search_fields = ['webhook__name', 'error_message']
    readonly_fields = ['created_at']
    