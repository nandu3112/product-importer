from django.shortcuts import render, redirect

# Create your views here.
from django.contrib import messages
from django.http import JsonResponse
import os
from django.core.files.storage import default_storage

from .services import CSVUploadService
from .models import ImportBatch

def upload_csv(request):
    """Handle CSV file upload"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        # Validate file type
        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a CSV file')
            return redirect('upload-csv')
        
        # Save file temporarily
        temp_path = default_storage.save(f'temp/{csv_file.name}', csv_file)
        full_path = default_storage.path(temp_path)
        
        try:
            # Validate and get exact count
            upload_service = CSVUploadService()
            is_valid, message, exact_count = upload_service.validate_and_count_records(full_path)
            
            if not is_valid:
                messages.error(request, message)
                default_storage.delete(temp_path)
                return redirect('upload-csv')
            
            if exact_count == 0:
                messages.error(request, 'File appears to be empty or cannot be read')
                default_storage.delete(temp_path)
                return redirect('upload-csv')
            
            # Create import batch with EXACT count
            user = request.user if request.user.is_authenticated else None
            batch = upload_service.create_import_batch(
                file_name=csv_file.name,
                total_records=exact_count,
                user=user
            )
            
            # Start processing
            task_id = upload_service.process_csv(full_path, batch.id, user)
            
            messages.success(
                request, 
                f'File uploaded successfully! Processing {exact_count:,} records in the background.'
            )
            
            # REDIRECT TO STATUS PAGE
            return redirect('upload-status', batch_id=batch.id)
            
        except Exception as e:
            messages.error(request, f'Upload failed: {str(e)}')
            if default_storage.exists(temp_path):
                default_storage.delete(temp_path)
        
        return redirect('upload-history')
    
    return render(request, 'uploads/upload.html')

def upload_history(request):
    """Show upload history"""
    batches = ImportBatch.objects.all().order_by('-created_at')[:20]
    return render(request, 'uploads/history.html', {'batches': batches})

def upload_status(request, batch_id):
    """Check upload processing status"""
    try:
        batch = ImportBatch.objects.get(id=batch_id)
        
        # Calculate progress correctly
        progress = 0
        if batch.total_records > 0:
            progress = int((batch.processed_records / batch.total_records) * 100)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'batch_id': batch.id,
                'status': batch.status,
                'processed': batch.processed_records,
                'total': batch.total_records,
                'successful': batch.successful_records,
                'failed': batch.failed_records,
                'progress': progress
            })
        
        return render(request, 'uploads/status.html', {
            'batch': batch,
            'progress': progress
        })
        
    except ImportBatch.DoesNotExist:
        messages.error(request, 'Upload batch not found')
        return redirect('upload-history')
    