from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required

@login_required
def upload_csv(request):
    return render(request, 'uploads/upload.html', {
        'message': 'CSV upload functionality coming soon!'
    })
