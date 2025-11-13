from django.contrib import admin

# Register your models here.
from .models import ImportBatch

@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'status', 'total_records', 'processed_records', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'completed_at']
    search_fields = ['file_name']
    
    def created_by_display(self, obj):
        return obj.created_by.username if obj.created_by else "Anonymous"
    created_by_display.short_description = 'Created By'
    
