import pandas as pd
import logging
from django.db import transaction, connection
from products.models import Product
from uploads.models import ImportBatch
import time

logger = logging.getLogger(__name__)

class BulkCSVProcessor:
    
    def __init__(self):
        self.batch_size = 5000
    
    def process_large_csv(self, file_path, batch_id, chunk_size=10000):
        """Optimized processing for very large files"""
        batch = ImportBatch.objects.get(id=batch_id)
        batch.status = 'processing'
        batch.save()
        
        total_processed = 0
        total_successful = 0
        errors = []
        
        try:
            for chunk_number, chunk in enumerate(pd.read_csv(file_path, chunksize=chunk_size)):
                chunk_successful, chunk_errors = self._process_chunk_bulk(chunk, batch_id)
                
                total_successful += chunk_successful
                total_processed += len(chunk)
                errors.extend(chunk_errors)
                
                # Update progress less frequently for better performance
                if chunk_number % 10 == 0:  # Update every 10 chunks
                    self._update_batch_progress(batch, total_processed, total_successful, len(errors))
                
                logger.info(f"Processed chunk {chunk_number}: {len(chunk)} records")
            
            # Final update
            self._update_batch_progress(batch, total_processed, total_successful, len(errors))
            batch.mark_completed()
            
            return total_successful, len(errors), errors
            
        except Exception as e:
            logger.error(f"Bulk processing failed: {e}")
            batch.mark_failed(str(e))
            raise
    
    def _process_chunk_bulk(self, chunk, batch_id):
        """Process chunk using bulk operations"""
        products_to_create = []
        products_to_update = []
        errors = []
        
        # Get existing SKUs for this chunk
        skus_in_chunk = []
        for _, row in chunk.iterrows():
            try:
                product_data = self._map_row_to_product(row)
                skus_in_chunk.append(product_data['sku'])
            except Exception as e:
                errors.append({'sku': 'Unknown', 'error': str(e)})
        
        # Fetch existing products in bulk
        existing_products = Product.objects.filter(sku__in=skus_in_chunk)
        existing_sku_map = {product.sku.upper(): product for product in existing_products}
        
        # Prepare bulk operations
        for index, row in chunk.iterrows():
            try:
                product_data = self._map_row_to_product(row)
                sku = product_data['sku']
                
                if sku in existing_sku_map:
                    # Update existing
                    existing_product = existing_sku_map[sku]
                    existing_product.name = product_data['name']
                    existing_product.description = product_data['description']
                    existing_product.is_active = product_data['is_active']
                    products_to_update.append(existing_product)
                else:
                    # Create new
                    products_to_create.append(Product(**product_data))
                    
            except Exception as e:
                errors.append({
                    'row': index + 2,
                    'sku': str(row.get('sku', 'Unknown')),
                    'error': str(e)
                })
        
        # Execute bulk operations
        with transaction.atomic():
            if products_to_create:
                Product.objects.bulk_create(products_to_create, batch_size=self.batch_size)
            
            if products_to_update:
                Product.objects.bulk_update(
                    products_to_update, 
                    ['name', 'description', 'is_active'], 
                    batch_size=self.batch_size
                )
        
        successful = len(products_to_create) + len(products_to_update)
        return successful, errors
    
    def _map_row_to_product(self, row):
        """Optimized row mapping"""
        row_dict = row.where(pd.notna(row), None).to_dict()
        
        # Fast SKU extraction
        sku = None
        for field in ['sku', 'SKU', 'product_sku']:
            if field in row_dict and row_dict[field]:
                sku = str(row_dict[field]).strip().upper()
                break
        
        if not sku:
            raise ValueError("No SKU found")
        
        # Fast name extraction
        name = "Unknown"
        for field in ['name', 'Name', 'product_name']:
            if field in row_dict and row_dict[field]:
                name = str(row_dict[field]).strip()[:255]
                break
        
        description = ""
        for field in ['description', 'Description']:
            if field in row_dict and row_dict[field]:
                description = str(row_dict[field]).strip()
                break
        
        return {
            'sku': sku,
            'name': name,
            'description': description,
            'is_active': True
        }
    
    def _update_batch_progress(self, batch, processed, successful, failed_count):
        """Update batch progress without frequent saves"""
        batch.processed_records = processed
        batch.successful_records = successful
        batch.failed_records = failed_count
        batch.save(update_fields=['processed_records', 'successful_records', 'failed_records'])
