from django.db import transaction
from django.db.models import Q
import logging
from .models import Product
from webhooks.services import WebhookService

logger = logging.getLogger(__name__)

class ProductService:
    @staticmethod
    def create_or_update_product(product_data: dict) -> tuple:
        """Create or update product with webhook triggers"""
        try:
            sku = product_data['sku']
            
            with transaction.atomic():
                # Find existing product (case-insensitive)
                existing_product = Product.objects.filter(sku__iexact=sku).first()
                
                if existing_product:
                    # Update existing product
                    for field, value in product_data.items():
                        if field != 'sku':  # Don't change SKU
                            setattr(existing_product, field, value)
                    existing_product.save()
                    
                    # Webhook will be triggered in the task
                    return existing_product, 'updated'
                else:
                    # Create new product
                    product = Product.objects.create(**product_data)
                    
                    # Webhook will be triggered in the task  
                    return product, 'created'
                    
        except Exception as e:
            logger.error(f"Error creating/updating product {product_data.get('sku')}: {e}")
            raise

class BulkProductService:
    @staticmethod
    def delete_all_products():
        """Delete all products with webhook triggers"""
        products = Product.objects.all()
        
        for product in products:
            WebhookService.send_webhook('product.deleted', {
                'product_id': product.id,
                'sku': product.sku,
                'name': product.name
            })
        
        total_products = products.count()
        products.delete()
        return total_products

class ProductSearchService:
    @staticmethod
    def search_products(
        search_term: str = None,
        sku: str = None,
        name: str = None,
        is_active: bool = None,
        page: int = 1,
        page_size: int = 50
    ):
        """Advanced product search with filtering"""
        from django.core.paginator import Paginator
        
        queryset = Product.objects.all()
        
        # Apply filters
        if search_term:
            queryset = queryset.filter(
                Q(sku__icontains=search_term) |
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term)
            )
        
        if sku:
            queryset = queryset.filter(sku__icontains=sku)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        # Pagination
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        return {
            'products': page_obj,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    