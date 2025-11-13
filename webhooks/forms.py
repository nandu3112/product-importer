from django import forms
from .models import Webhook

class WebhookForm(forms.ModelForm):
    class Meta:
        model = Webhook
        fields = ['name', 'url', 'event_type', 'is_active', 'secret_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://example.com/webhook'}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'secret_key': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Optional secret for signing webhooks'
            }),
        }
        help_texts = {
            'secret_key': 'Leave blank if you don\'t want to sign webhooks',
        }
    
    def clean_url(self):
        url = self.cleaned_data['url']
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError('URL must start with http:// or https://')
        return url
    