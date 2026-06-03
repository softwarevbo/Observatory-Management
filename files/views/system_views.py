from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import SystemSettings
from django import forms

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ['max_file_size_gb']
        widgets = {
            'max_file_size_gb': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 50})
        }

@login_required
def system_settings(request):
    if not request.user.is_admin:
        messages.error(request, "Access denied. Admins only.")
        return redirect('tasks:dashboard')
    
    config = SystemSettings.objects.first()
    if not config:
        config = SystemSettings.objects.create()
    
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "System settings updated successfully.")
            return redirect('files:system_settings')
    else:
        form = SystemSettingsForm(instance=config)
    
    return render(request, 'files/system_settings.html', {
        'form': form,
        'config': config
    })
