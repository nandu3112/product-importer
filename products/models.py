from django.db import models

# Create your models here.
class Product(models.Model):
    sku = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Stock Keeping Unit (case-insensitive)"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sku} - {self.name}"
    
    def save(self, *args, **kwargs):
        self.sku = self.sku.upper()
        super().save(*args, **kwargs)
