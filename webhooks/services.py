import json
import hmac
import hashlib
import time
from django.conf import settings
from django.utils import timezone
from celery import shared_task
import logging
from .models import Webhook, WebhookLog

logger = logging.getLogger(__name__)

class WebhookService:
    @staticmethod
    def send_webhook(event_type: str, payload: dict):
        """Send webhook for specific event type to all active webhooks"""
        active_webhooks = Webhook.objects.filter(
            event_type=event_type,
            is_active=True
        )
        
        for webhook in active_webhooks:
            WebhookService.send_single_webhook.delay(webhook.id, event_type, payload)
        
        logger.info(f"Triggered {active_webhooks.count()} webhooks for event: {event_type}")
    
    @staticmethod
    @shared_task(bind=True, max_retries=3)
    def send_single_webhook(self, webhook_id: int, event_type: str, payload: dict):
        """Send a single webhook with retry logic"""
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            start_time = time.time()
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Acme-Products/1.0',
                'X-Webhook-Event': event_type,
                'X-Webhook-ID': str(webhook.id),
                'X-Webhook-Timestamp': str(int(time.time())),
            }
            
            # Add signature if secret key is set
            payload_str = json.dumps(payload, sort_keys=True)
            if webhook.secret_key:
                signature = hmac.new(
                    webhook.secret_key.encode('utf-8'),
                    payload_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Webhook-Signature'] = f"sha256={signature}"
            
            # Send request
            response = requests.post(
                webhook.url,
                data=payload_str,
                headers=headers,
                timeout=30  # 30 second timeout
            )
            
            duration = time.time() - start_time
            
            # Log the webhook attempt
            WebhookLog.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                response_code=response.status_code,
                response_body=response.text[:1000],  # Limit response body size
                duration=duration,
                is_success=200 <= response.status_code < 300
            )
            
            # Raise for status to trigger retry for non-2xx responses
            if response.status_code >= 400:
                raise requests.exceptions.HTTPError(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            
            logger.info(f"Webhook {webhook_id} delivered successfully in {duration:.2f}s")
            
            return {
                'webhook_id': webhook_id,
                'status_code': response.status_code,
                'duration': duration,
                'success': True
            }
            
        except requests.exceptions.RequestException as e:
            # Log the failure
            if 'webhook' in locals():
                WebhookLog.objects.create(
                    webhook=webhook,
                    event_type=event_type,
                    payload=payload,
                    error_message=str(e),
                    is_success=False
                )
            
            # Retry with exponential backoff
            retry_count = self.request.retries
            if retry_count < self.max_retries:
                retry_delay = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                logger.warning(f"Webhook {webhook_id} failed, retrying in {retry_delay}s: {e}")
                raise self.retry(countdown=retry_delay, exc=e)
            
            logger.error(f"Webhook {webhook_id} failed after {retry_count} retries: {e}")
            
            # Update log with final failure
            if 'webhook' in locals():
                log = WebhookLog.objects.filter(
                    webhook=webhook,
                    event_type=event_type
                ).order_by('-created_at').first()
                if log:
                    log.retry_count = retry_count + 1
                    log.save()
            
            raise
    
    @staticmethod
    def test_webhook(webhook_id: int) -> dict:
        """Test a webhook with sample data and return detailed results"""
        try:
            webhook = Webhook.objects.get(id=webhook_id)
            start_time = time.time()
            
            sample_payload = {
                "event": event_type,
                "data": {
                    "message": "This is a test webhook from Acme Products",
                    "timestamp": timezone.now().isoformat(),
                    "webhook_id": webhook_id,
                    "test": True
                },
                "webhook_event": "webhook.test"
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Acme-Products/1.0',
                'X-Webhook-Event': 'webhook.test',
            }
            
            if webhook.secret_key:
                signature = hmac.new(
                    webhook.secret_key.encode('utf-8'),
                    json.dumps(sample_payload).encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Webhook-Signature'] = f"sha256={signature}"
            
            response = requests.post(
                webhook.url,
                json=sample_payload,
                headers=headers,
                timeout=10
            )
            
            duration = time.time() - start_time
            
            # Log test attempt
            WebhookLog.objects.create(
                webhook=webhook,
                event_type='webhook.test',
                payload=sample_payload,
                response_code=response.status_code,
                response_body=response.text[:500],
                duration=duration,
                is_success=200 <= response.status_code < 300
            )
            
            return {
                'success': 200 <= response.status_code < 300,
                'status_code': response.status_code,
                'response_time': round(duration, 2),
                'response_body': response.text[:500],
                'message': 'Webhook test completed successfully' if 200 <= response.status_code < 300 else 'Webhook test failed'
            }
            
        except Exception as e:
            logger.error(f"Webhook test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Webhook test failed - could not connect to URL'
            }
    
    @staticmethod
    def get_webhook_payload(event_type: str, data: dict) -> dict:
        """Generate standardized webhook payload"""
        return {
            "event": event_type,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "version": "1.0"
        }
