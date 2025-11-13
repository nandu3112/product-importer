from django.db import models

# Create your models here.
from django.utils import timezone
import json

class Webhook(models.Model):
    EVENT_CHOICES = [
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'), 
        ('product.deleted', 'Product Deleted'),
        ('import.started', 'Import Started'),
        ('import.completed', 'Import Completed'),
        ('import.failed', 'Import Failed'),
    ]
    
    name = models.CharField(max_length=255, help_text="Descriptive name for this webhook")
    url = models.URLField(help_text="URL to send webhook payloads to")
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    is_active = models.BooleanField(default=True)
    secret_key = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Optional secret for signing webhooks (HMAC)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def _str_(self):
        return f"{self.name} - {self.event_type}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'is_active']),
            models.Index(fields=['is_active']),
        ]

class WebhookLog(models.Model):
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='logs')
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    duration = models.FloatField(help_text="Response time in seconds", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    retry_count = models.IntegerField(default=0)
    is_success = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', 'created_at']),
            models.Index(fields=['is_success', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} - {self.created_at}"
    