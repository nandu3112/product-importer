import pandas as pd
import chardet
import os
import logging
from django.core.files.storage import default_storage
from uploads.models import ImportBatch
from .tasks import process_csv_upload  # Only import the main task

logger = logging.getLogger(__name__)

class CSVUploadService:
    
    def detect_encoding(self, file_path):
        """Detect file encoding"""
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            return result['encoding']
    
    def validate_csv_structure(self, file_path):
        """Validate CSV structure"""
        try:
            encoding = self.detect_encoding(file_path)
            df = pd.read_csv(file_path, nrows=5, encoding=encoding)
            
            if df.empty:
                return False, "CSV file is empty"
            
            headers = [str(header).lower().strip() for header in df.columns]
            
            sku_columns = ['sku', 'product_sku', 'item_sku', 'code', 'id']
            has_sku = any(sku_col in headers for sku_col in sku_columns)
            
            if not has_sku:
                return False, "No SKU column found in CSV"
                
            return True, "CSV structure is valid"
            
        except Exception as e:
            return False, f"CSV validation failed: {str(e)}"
    
    def validate_and_count_records(self, file_path):
        """Validate CSV and return exact record count"""
        try:
            encoding = self.detect_encoding(file_path)
            df = pd.read_csv(file_path, encoding=encoding)
            exact_count = len(df)
            
            # Check for SKU column
            headers = [str(header).lower().strip() for header in df.columns]
            sku_columns = ['sku', 'product_sku', 'item_sku', 'code', 'id']
            has_sku = any(sku_col in headers for sku_col in sku_columns)
            
            if not has_sku:
                return False, "No SKU column found in CSV", 0
                
            return True, "CSV structure is valid", exact_count
            
        except Exception as e:
            return False, f"CSV validation failed: {str(e)}", 0
    
    def process_csv(self, file_path, batch_id, user=None):
        """Process CSV file using the main task"""
        try:
            # Use the main processing task
            task = process_csv_upload.delay(batch_id, file_path, user.id if user else None)
            return task.id
            
        except Exception as e:
            logger.error(f"Failed to start processing: {e}")
            raise
    
    def create_import_batch(self, file_name, total_records, user=None):
        """Create a new import batch record"""
        if user and user.is_authenticated and not user.is_anonymous:
            return ImportBatch.objects.create(
                file_name=file_name,
                total_records=total_records,
                created_by=user
            )
        else:
            return ImportBatch.objects.create(
                file_name=file_name,
                total_records=total_records
            )
        