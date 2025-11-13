import os
import pandas as pd
from celery import shared_task
from django.core.files.storage import default_storage
from .models import ImportBatch
from .task_services import CSVTaskService
import time
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
import psutil
import gc

logger = logging.getLogger(__name__)

def send_progress_update(batch_id, status, processed, total, successful, failed):
    """Send progress update via WebSocket"""
    try:
        # Only try WebSocket if Channels is configured
        if hasattr(settings, 'CHANNEL_LAYERS'):
            channel_layer = get_channel_layer()
            if channel_layer:
                progress = int((processed / total) * 100) if total > 0 else 0
                
                logger.info(f"📤 Sending progress update: {processed}/{total} ({progress}%)")
                
                async_to_sync(channel_layer.group_send)(
                    f'upload_progress_{batch_id}',
                    {
                        'type': 'progress_update',
                        'batch_id': str(batch_id),
                        'status': status,
                        'processed': processed,
                        'total': total,
                        'successful': successful,
                        'failed': failed,
                        'progress': progress
                    }
                )
                logger.debug(f"Progress update sent successfully")
            else:
                logger.warning("Channel layer not available")
        else:
            logger.debug("Channels not configured")
            
    except Exception as e:
        logger.error(f"❌ Progress update failed: {e}")

@shared_task(bind=True)
def process_csv_upload(self, batch_id, file_path, user_id=None):
    """
    Main CSV processing task with real-time progress updates
    """
    try:
        batch = ImportBatch.objects.get(id=batch_id)
        task_service = CSVTaskService()
        
        batch.status = 'processing'
        batch.save()
        
        # Monitor memory usage
        process = psutil.Process()
        start_memory = process.memory_info().rss
        
        logger.info(f"Starting CSV processing for batch {batch_id}")
        
        # Send initial progress and trigger webhook
        send_progress_update(batch_id, 'processing', 0, batch.total_records, 0, 0)
        
        # Trigger import started webhook
        from webhooks.services import WebhookService
        WebhookService.send_webhook('import.started', {
            'batch_id': batch_id,
            'file_name': batch.file_name,
            'total_records': batch.total_records,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        encoding = task_service.detect_encoding(file_path)
        
        # Read the entire file to get accurate count
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            actual_total = len(df)
            
            # Update batch with actual count
            if actual_total != batch.total_records:
                logger.info(f"Updating record count from {batch.total_records} to {actual_total}")
                batch.total_records = actual_total
                batch.save()
            
        except Exception as e:
            logger.error(f"Failed to read CSV file: {e}")
            batch.mark_failed(f"Failed to read CSV file: {e}")
            send_progress_update(batch_id, 'failed', 0, 0, 0, 0)
            
            # Trigger import failed webhook
            WebhookService.send_webhook('import.failed', {
                'batch_id': batch_id,
                'file_name': batch.file_name,
                'error': str(e),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
            if os.path.exists(file_path):
                os.remove(file_path)
            return {
                'batch_id': batch_id,
                'successful': 0,
                'failed': 1,
                'status': 'failed',
                'error': str(e)
            }
        
        # Decide chunk size based on file size
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # Files larger than 50MB
            chunk_size = 5000
            logger.info(f"Using large file mode: {file_size/1024/1024:.2f}MB, chunk size: {chunk_size}")
        else:
            chunk_size = 1000
            logger.info(f"Using standard mode: {file_size/1024/1024:.2f}MB, chunk size: {chunk_size}")
        
        total_processed = 0
        total_successful = 0
        errors = []
        
        # Process in appropriate chunks
        for chunk_number, chunk in enumerate(pd.read_csv(file_path, chunksize=chunk_size, encoding=encoding)):
            chunk_errors = []
            
            for index, row in chunk.iterrows():
                try:
                    product_data = task_service._map_row_to_product(row)
                    product, action = task_service._create_or_update_product(product_data)
                    total_successful += 1
                    
                    # Trigger product webhook based on action
                    if action == 'created':
                        WebhookService.send_webhook('product.created', {
                            'product_id': product.id,
                            'sku': product.sku,
                            'name': product.name,
                            'action': 'created'
                        })
                    else:
                        WebhookService.send_webhook('product.updated', {
                            'product_id': product.id,
                            'sku': product.sku,
                            'name': product.name,
                            'action': 'updated'
                        })
                    
                except Exception as e:
                    chunk_errors.append({
                        'row': total_processed + index + 2,
                        'sku': str(row.get('sku', row.get('SKU', 'Unknown'))),
                        'error': str(e)
                    })
                    logger.debug(f"Row {total_processed + index} error: {e}")
            
            errors.extend(chunk_errors)
            total_processed += len(chunk)
            
            # Update batch progress
            batch.processed_records = total_processed
            batch.successful_records = total_successful
            batch.failed_records = len(errors)
            batch.errors = errors[:100]
            batch.save()
            
            # Send progress update
            send_progress_update(
                batch_id, 
                'processing', 
                total_processed, 
                actual_total,
                total_successful, 
                len(errors)
            )
            
            # Update Celery task state
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': total_processed,
                    'total': actual_total,
                    'successful': total_successful,
                    'failed': len(errors),
                    'batch_id': batch_id
                }
            )
            
            # Memory management for large files
            if file_size > 10 * 1024 * 1024:
                current_memory = process.memory_info().rss
                memory_used = (current_memory - start_memory) / 1024 / 1024
                
                if memory_used > 500:  # If using more than 500MB
                    logger.warning(f"High memory usage: {memory_used:.2f}MB, forcing garbage collection")
                    gc.collect()
                
                time.sleep(0.05)
        
        # Final update
        batch.processed_records = actual_total
        batch.successful_records = total_successful
        batch.failed_records = len(errors)
        batch.errors = errors
        batch.mark_completed()
        batch.save()
        
        # Log final statistics
        final_memory = process.memory_info().rss
        memory_used = (final_memory - start_memory) / 1024 / 1024
        
        logger.info(f"✅ Processing completed: {total_successful} successful, {len(errors)} failed")
        
        send_progress_update(
            batch_id, 
            'completed', 
            actual_total, 
            actual_total, 
            total_successful, 
            len(errors)
        )
        
        # Trigger import completed webhook
        WebhookService.send_webhook('import.completed', {
            'batch_id': batch_id,
            'file_name': batch.file_name,
            'total_records': actual_total,
            'successful': total_successful,
            'failed': len(errors),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Clean up file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return {
            'batch_id': batch_id,
            'successful': total_successful,
            'failed': len(errors),
            'status': 'completed',
            'memory_used_mb': round(memory_used, 2)
        }
        
    except Exception as e:
        logger.error(f"CSV processing failed: {e}")
        batch = ImportBatch.objects.get(id=batch_id)
        batch.mark_failed(str(e))
        
        send_progress_update(batch_id, 'failed', 0, 0, 0, 0)
        
        # Trigger import failed webhook
        from webhooks.services import WebhookService
        WebhookService.send_webhook('import.failed', {
            'batch_id': batch_id,
            'file_name': batch.file_name,
            'error': str(e),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        raise
