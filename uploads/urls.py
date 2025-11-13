from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_csv, name='upload-csv'),
    path('history/', views.upload_history, name='upload-history'),
    path('status/<int:batch_id>/', views.upload_status, name='upload-status'),
]
