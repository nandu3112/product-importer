import pandas as pd
import logging
from django.db import connection

from uploads.models import ImportBatch
import time


logger = logging.getLogger(__name__)

class UltraFastCSVProcessor:
    
    def _init_(self):
        self.batch_size = 10000
    
    def process_large_csv(self, file_path, batch_id, chunk_size=50000):
        """Ultra-fast processing using direct SQL"""
        batch = ImportBatch.objects.get(id=batch_id)
        batch.status = 'processing'
        batch.save()
        
        start_time = time.time()
        total_processed = 0
        total_successful = 0
        errors = []
        
        try:
            # Optimized pandas reading
            dtype_spec = {
                'sku': 'string', 'SKU': 'string', 'product_sku': 'string',
                'name': 'string', 'Name': 'string', 'product_name': 'string',
                'description': 'string', 'Description': 'string',
                'item_sku': 'string', 'code': 'string', 'id': 'string',
                'item_name': 'string', 'title': 'string', 'product': 'string',
                'desc': 'string', 'product_description': 'string'
            }
            
            for chunk_number, chunk in enumerate(
                pd.read_csv(
                    file_path, 
                    chunksize=chunk_size, 
                    dtype=dtype_spec, 
                    low_memory=False,
                    usecols=lambda x: any(keyword in x.lower() for keyword in 
                                        ['sku', 'name', 'description', 'product', 'item', 'code', 'id', 'title', 'desc'])
                )
            ):
                logger.info(f"Processing chunk {chunk_number} with {len(chunk)} records")
                
                chunk_successful, chunk_errors = self._process_chunk_direct_sql(chunk)
                
                total_successful += chunk_successful
                total_processed += len(chunk)
                errors.extend(chunk_errors)
                
                # Update progress every chunk for large files
                batch.processed_records = total_processed
                batch.successful_records = total_successful
                batch.failed_records = len(errors)
                batch.save(update_fields=['processed_records', 'successful_records', 'failed_records'])
                
                logger.info(f"Chunk {chunk_number} completed: {chunk_successful} successful, {len(chunk_errors)} errors")
            
            # Final update
            batch_time = time.time() - start_time
            batch.mark_completed()
            
            logger.info(f"Total processing time: {batch_time:.2f} seconds for {total_processed} records")
            
            return total_successful, len(errors), errors
            
        except Exception as e:
            logger.error(f"Bulk processing failed: {e}")
            batch.mark_failed(str(e))
            raise
    
    def _process_chunk_direct_sql(self, chunk):
        """Use raw SQL for maximum performance"""
        errors = []
        records = []
        
        # Fast extraction
        for index, row in chunk.iterrows():
            try:
                sku, name, description = self._ultra_fast_extract_fields(row)
                records.append((sku, name, description))
            except Exception as e:
                errors.append({
                    'row': index + 2,
                    'sku': str(row.get('sku', 'Unknown')),
                    'error': str(e)
                })
        
        if not records:
            return 0, errors
        
        # Use bulk SQL operations
        successful = self._bulk_upsert_postgresql(records) if connection.vendor == 'postgresql' else self._bulk_upsert_sqlite(records)
        
        return successful, errors
    
    def _ultra_fast_extract_fields(self, row):
        """Ultra-fast field extraction"""
        row_dict = dict(row.items())
        
        # SKU extraction - single pass
        sku = None
        for field, value in row_dict.items():
            if value is not None and any(keyword in field.lower() for keyword in ['sku', 'code', 'id']):
                sku = str(value).strip().upper()
                if sku and sku != 'NAN':
                    break
        
        if not sku:
            raise ValueError("No valid SKU found")
        
        # Name extraction
        name = f"Product {sku}"  # Default
        for field, value in row_dict.items():
            if value is not None and any(keyword in field.lower() for keyword in ['name', 'title', 'product']):
                name_val = str(value).strip()
                if name_val and name_val != 'NAN':
                    name = name_val[:255]
                    break
        
        # Description extraction
        description = ""
        for field, value in row_dict.items():
            if value is not None and any(keyword in field.lower() for keyword in ['description', 'desc']):
                desc_val = str(value).strip()
                if desc_val and desc_val != 'NAN':
                    description = desc_val
                    break
        
        return sku, name, description
    
    def _bulk_upsert_postgresql(self, records):
        """PostgreSQL-specific bulk UPSERT"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Create temp table
            cursor.execute("""
                CREATE TEMPORARY TABLE temp_products_upsert (
                    sku VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255),
                    description TEXT
                ) ON COMMIT DROP
            """)
            
            # Bulk insert into temp table
            cursor.executemany(
                "INSERT INTO temp_products_upsert (sku, name, description) VALUES (%s, %s, %s)",
                records
            )
            
            # UPSERT from temp table
            cursor.execute("""
                INSERT INTO products_product (sku, name, description, is_active, created_at, updated_at)
                SELECT sku, name, description, true, NOW(), NOW()
                FROM temp_products_upsert
                ON CONFLICT (sku) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
            """)
            
            return cursor.rowcount
    
    def _bulk_upsert_sqlite(self, records):
        """SQLite-specific bulk operations"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            # For SQLite, use INSERT OR REPLACE
            placeholders = ','.join(['?'] * 6)
            sql = f"""
                INSERT OR REPLACE INTO products_product 
                (sku, name, description, is_active, created_at, updated_at)
                VALUES ({placeholders})
            """
            
            # Prepare records with all required fields
            final_records = []
            for sku, name, description in records:
                final_records.append((sku, name, description, True, 'NOW', 'NOW'))
            
            cursor.executemany(sql, final_records)
            return len(final_records)
        