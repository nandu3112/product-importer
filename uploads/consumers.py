import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(_name_)

class UploadProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.batch_id = self.scope['url_route']['kwargs']['batch_id']
        self.room_group_name = f'upload_progress_{self.batch_id}'

        logger.info(f"WebSocket connecting for batch {self.batch_id}")
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected for batch {self.batch_id}")

        # Send initial progress
        await self.send_progress()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting for batch {self.batch_id}, code: {close_code}")
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_batch_data(self):
        """Get batch data from database"""
        try:
            from .models import ImportBatch
            batch = ImportBatch.objects.get(id=self.batch_id)
            progress = 0
            if batch.total_records > 0:
                progress = int((batch.processed_records / batch.total_records) * 100)
            
            return {
                'batch_id': str(batch.id),
                'status': batch.status,
                'processed': batch.processed_records,
                'total': batch.total_records,
                'successful': batch.successful_records,
                'failed': batch.failed_records,
                'progress': progress
            }
        except Exception as e:
            logger.error(f"Error getting batch data: {e}")
            return None

    async def send_progress(self):
        """Send current progress to client"""
        batch_data = await self.get_batch_data()
        
        if batch_data:
            progress_data = {
                'type': 'progress_update',
                **batch_data
            }
            await self.send(text_data=json.dumps(progress_data))
            logger.info(f"Sent initial progress for batch {self.batch_id}")
        else:
            error_data = {
                'type': 'error',
                'message': 'Upload batch not found'
            }
            await self.send(text_data=json.dumps(error_data))

    async def progress_update(self, event):
        """Receive progress update from room group"""
        logger.info(f"Sending progress update for batch {self.batch_id}: {event}")
        await self.send(text_data=json.dumps(event))
        