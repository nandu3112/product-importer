import pandas as pd
import chardet
import os
import logging

from products.models import Product
from uploads.models import ImportBatch

logger = logging.getLogger(__name__)

class CSVFileUpload:
    
    def detect_encoding(self, file_path):
        """Detect file encoding"""
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding']
    
    def validate_csv_structure(self, file_path):
        """Validate CSV structure before processing"""
        try:
            encoding = self.detect_encoding(file_path)
            df = pd.read_csv(file_path, nrows=5, encoding=encoding)
            
            if df.empty:
                return False, "CSV file is empty"
            
            headers = [str(header).lower().strip() for header in df.columns]
            
            sku_columns = ['sku', 'product_sku', 'item_sku', 'code', 'id']
            has_sku = any(sku_col in headers for sku_col in sku_columns)
            
            if not has_sku:
                return False, "No SKU column found in CSV. Looking for columns like: sku, product_sku, item_sku, code, id"
                
            return True, "CSV structure is valid"
            
        except Exception as e:
            return False, f"CSV validation failed: {str(e)}"
    
    def process_csv_sync(self, file_path, batch_id, user=None):
        """Process CSV file synchronously (for small files)"""
        try:
            batch = ImportBatch.objects.get(id=batch_id)
            batch.status = 'processing'
            batch.save()
            
            encoding = self.detect_encoding(file_path)
            df = pd.read_csv(file_path, encoding=encoding)
            
            successful = 0
            failed = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Map row data to product fields
                    product_data = self._map_row_to_product(row)
                    
                    # Create or update product
                    product, created = self._create_or_update_product(product_data)
                    successful += 1
                    
                except Exception as e:
                    failed += 1
                    errors.append({
                        'row': index + 2,  # +2 for header and 1-based indexing
                        'sku': str(row.get('sku', row.get('SKU', 'Unknown'))),
                        'error': str(e)
                    })
                    logger.warning(f"Row {index} error: {e}")
                
                # Update progress every 100 records
                if (index + 1) % 100 == 0:
                    batch.processed_records = index + 1
                    batch.successful_records = successful
                    batch.failed_records = failed
                    batch.errors = errors[:50]  # Keep only recent errors
                    batch.save()
            
            # Final update
            batch.processed_records = len(df)
            batch.successful_records = successful
            batch.failed_records = failed
            batch.errors = errors
            batch.mark_completed()
            
            # Clean up file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return successful, failed, errors
            
        except Exception as e:
            logger.error(f"CSV processing failed: {e}")
            batch.mark_failed(str(e))
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
    
    def _map_row_to_product(self, row):
        """Map CSV row to product data"""
        # Convert row to dictionary and handle NaN values
        row_dict = row.where(pd.notna(row), None).to_dict()
        
        # Try different column names for SKU
        sku = None
        for sku_field in ['sku', 'SKU', 'product_sku', 'item_sku', 'code', 'id']:
            if sku_field in row_dict and row_dict[sku_field]:
                sku = str(row_dict[sku_field]).strip().upper()
                break
        
        if not sku:
            raise ValueError("No SKU found in row")
        
        # Try different column names for name
        name = None
        for name_field in ['name', 'Name', 'product_name', 'item_name', 'title', 'product']:
            if name_field in row_dict and row_dict[name_field]:
                name = str(row_dict[name_field]).strip()
                break
        
        if not name:
            name = f"Product {sku}"  # Default name if not provided
        
        # Try different column names for description
        description = ""
        for desc_field in ['description', 'Description', 'desc', 'product_description']:
            if desc_field in row_dict and row_dict[desc_field]:
                description = str(row_dict[desc_field]).strip()
                break
        
        return {
            'sku': sku,
            'name': name[:255],  # Ensure it fits in CharField
            'description': description,
            'is_active': True
        }
    
    def _create_or_update_product(self, product_data):
        """Create or update product, handling duplicates case-insensitively"""
        sku = product_data['sku']
        
        # Find existing product (case-insensitive)
        existing_product = Product.objects.filter(sku__iexact=sku).first()
        
        if existing_product:
            # Update existing product
            existing_product.name = product_data['name']
            existing_product.description = product_data['description']
            existing_product.is_active = product_data['is_active']
            existing_product.save()
            return existing_product, False
        else:
            # Create new product
            product = Product.objects.create(**product_data)
            return product, True
    
    def create_import_batch(self, file_name, total_records, user=None):
        """Create a new import batch record - handle None user gracefully"""
        # Only set created_by if user is authenticated and not anonymous
        if user and user.is_authenticated and not user.is_anonymous:
            return ImportBatch.objects.create(
                file_name=file_name,
                total_records=total_records,
                created_by=user
            )
        else:
            # Create without user assignment
            return ImportBatch.objects.create(
                file_name=file_name,
                total_records=total_records
                # created_by is left as NULL
            )
        