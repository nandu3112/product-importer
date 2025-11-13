from django.shortcuts import render, redirect, get_object_or_404

# Create your views here.
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Webhook, WebhookLog
from .services import WebhookService
from .forms import WebhookForm

class WebhookListView(ListView):
    model = Webhook
    template_name = 'webhooks/list.html'
    context_object_name = 'webhooks'
    
    def get_queryset(self):
        return Webhook.objects.all().order_by('-created_at')

class WebhookCreateView(CreateView):
    model = Webhook
    form_class = WebhookForm
    template_name = 'webhooks/form.html'
    success_url = reverse_lazy('webhook-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Webhook created successfully!')
        return super().form_valid(form)

class WebhookUpdateView(UpdateView):
    model = Webhook
    form_class = WebhookForm
    template_name = 'webhooks/form.html'
    success_url = reverse_lazy('webhook-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Webhook updated successfully!')
        return super().form_valid(form)

class WebhookDeleteView(DeleteView):
    model = Webhook
    template_name = 'webhooks/confirm_delete.html'
    success_url = reverse_lazy('webhook-list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Webhook deleted successfully!')
        return super().delete(request, *args, **kwargs)

@require_http_methods(["POST"])
def test_webhook(request, pk):
    """Test a webhook configuration"""
    webhook = get_object_or_404(Webhook, pk=pk)
    
    result = WebhookService.test_webhook(webhook.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)
    
    if result['success']:
        messages.success(request, f"Webhook test successful! Response time: {result['response_time']}s")
    else:
        messages.error(request, f"Webhook test failed: {result.get('message', 'Unknown error')}")
    
    return redirect('webhook-list')

@require_http_methods(["POST"])
def toggle_webhook(request, pk):
    """Toggle webhook active status"""
    webhook = get_object_or_404(Webhook, pk=pk)
    webhook.is_active = not webhook.is_active
    webhook.save()
    
    status = "enabled" if webhook.is_active else "disabled"
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_active': webhook.is_active,
            'message': f'Webhook {status} successfully'
        })
    
    messages.success(request, f'Webhook {status} successfully')
    return redirect('webhook-list')

def webhook_logs(request, pk):
    """View logs for a specific webhook"""
    webhook = get_object_or_404(Webhook, pk=pk)
    logs = webhook.logs.all().order_by('-created_at')[:50]
    
    return render(request, 'webhooks/logs.html', {
        'webhook': webhook,
        'logs': logs
    })
