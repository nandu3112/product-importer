from django.shortcuts import render, redirect

# Create your views here.
from django.contrib import messages
from django.http import JsonResponse
import os
import pandas as pd
from django.core.files.storage import default_storage

from .services import CSVFileUpload
from .models import ImportBatch

def upload_csv(request):
    """Handle CSV file upload"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
    
        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a CSV file')
            return redirect('upload-csv')
    
        temp_path = default_storage.save(f'temp/{csv_file.name}', csv_file)
        full_path = default_storage.path(temp_path)
        
        try:
            upload_service = CSVFileUpload()
            is_valid, message = upload_service.validate_csv_structure(full_path)
            
            if not is_valid:
                messages.error(request, message)
                default_storage.delete(temp_path)
                return redirect('upload-csv')
            
            # Count total records (excluding header)
            encoding = upload_service.detect_encoding(full_path)
            df = pd.read_csv(full_path, encoding=encoding)
            total_records = len(df)
            
            # Create import batch - pass user only if authenticated
            user = request.user if request.user.is_authenticated else None
            batch = upload_service.create_import_batch(
                file_name=csv_file.name,
                total_records=total_records,
                user=user
            )
            
            # Process CSV synchronously, make this async later
            successful, failed, errors = upload_service.process_csv_sync(
                full_path, batch.id, user
            )
            
            messages.success(
                request, 
                f'Successfully processed {successful} products! {failed} failed.'
            )
            
            if errors:
                error_messages = [f"Row {e['row']} (SKU: {e['sku']}): {e['error']}" for e in errors[:5]]
                for error_msg in error_messages:
                    messages.warning(request, error_msg)
                if len(errors) > 5:
                    messages.info(request, f"... and {len(errors) - 5} more errors")
            
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
    batch = ImportBatch.objects.get(id=batch_id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'batch_id': batch.id,
            'status': batch.status,
            'processed': batch.processed_records,
            'total': batch.total_records,
            'successful': batch.successful_records,
            'failed': batch.failed_records,
            'progress': int((batch.processed_records / batch.total_records) * 100) if batch.total_records > 0 else 0
        })
    
    return render(request, 'uploads/status.html', {'batch': batch})
