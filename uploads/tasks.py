import os
import pandas as pd
from celery import shared_task
from django.core.files.storage import default_storage
from .models import ImportBatch

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from uploads.bulk_services import UltraFastCSVProcessor


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

@shared_task(bind=True, max_retries=3)
def process_csv_upload(self, batch_id, file_path, user_id=None):
    """Optimized task for fast CSV processing"""
    try:
        logger.info(f"Starting ultra-fast processing for batch {batch_id}")
        
        processor = UltraFastCSVProcessor()
        successful, failed_count, errors = processor.process_large_csv(
            file_path, 
            batch_id, 
            chunk_size=50000  # Larger chunks for speed
        )
        
        # Clean up file after processing
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.info(f"Completed batch {batch_id}: {successful} successful, {failed_count} failed")
        return {
            'batch_id': batch_id,
            'successful': successful,
            'failed': failed_count,
            'total_errors': len(errors)
        }
        
    except Exception as e:
        logger.error(f"Task failed for batch {batch_id}: {e}")
        
        # Clean up file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # Update batch status
        try:
            batch = ImportBatch.objects.get(id=batch_id)
            batch.mark_failed(str(e))
        except ImportBatch.DoesNotExist:
            pass
            
        raise
