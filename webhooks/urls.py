from django.urls import path
from . import views

urlpatterns = [
    path('', views.WebhookListView.as_view(), name='webhook-list'),
    path('create/', views.WebhookCreateView.as_view(), name='webhook-create'),
    path('<int:pk>/update/', views.WebhookUpdateView.as_view(), name='webhook-update'),
    path('<int:pk>/delete/', views.WebhookDeleteView.as_view(), name='webhook-delete'),
    path('<int:pk>/test/', views.test_webhook, name='webhook-test'),
    path('<int:pk>/toggle/', views.toggle_webhook, name='webhook-toggle'),
    path('<int:pk>/logs/', views.webhook_logs, name='webhook-logs'),
]
