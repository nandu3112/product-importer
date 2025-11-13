import pandas as pd
import chardet
import os
import logging
from django.core.files.storage import default_storage
from products.models import Product
from uploads.models import ImportBatch

logger = logging.getLogger(__name__)

class CSVTaskService:
    
    def detect_encoding(self, file_path):
        """Detect file encoding"""
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding']
    
    def _map_row_to_product(self, row):
        """Map CSV row to product data"""
        row_dict = row.where(pd.notna(row), None).to_dict()
        
        sku = None
        for sku_field in ['sku', 'SKU', 'product_sku', 'item_sku', 'code', 'id']:
            if sku_field in row_dict and row_dict[sku_field]:
                sku = str(row_dict[sku_field]).strip().upper()
                break
        
        if not sku:
            raise ValueError("No SKU found in row")
        
        name = None
        for name_field in ['name', 'Name', 'product_name', 'item_name', 'title', 'product']:
            if name_field in row_dict and row_dict[name_field]:
                name = str(row_dict[name_field]).strip()
                break
        
        if not name:
            name = f"Product {sku}"
        
        description = ""
        for desc_field in ['description', 'Description', 'desc', 'product_description']:
            if desc_field in row_dict and row_dict[desc_field]:
                description = str(row_dict[desc_field]).strip()
                break
        
        return {
            'sku': sku,
            'name': name[:255],
            'description': description,
            'is_active': True
        }
    
    def _create_or_update_product(self, product_data):
        """Create or update product, handling duplicates case-insensitively"""
        sku = product_data['sku']
        
        existing_product = Product.objects.filter(sku__iexact=sku).first()
        
        if existing_product:
            existing_product.name = product_data['name']
            existing_product.description = product_data['description']
            existing_product.is_active = product_data['is_active']
            existing_product.save()
            return existing_product, False
        else:
            product = Product.objects.create(**product_data)
            return product, True
        