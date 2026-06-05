from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import SystemSettings
from django import forms

"""
This module processes system settings configuration dashboards.
"""

class SystemSettingsForm(forms.ModelForm):
    """Form to adjust maximum upload constraints bounds."""
    class Meta:
        model = SystemSettings
        fields = ['max_file_size_gb']
        widgets = {
            'max_file_size_gb': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 50})
        }

@login_required
def system_settings(request):
    """
    Validates user credentials and redirects admin users to the system settings panels page.
    """
    if not request.user.is_admin:
        messages.error(request, "Access denied. Admins only.")
        return redirect('tasks:dashboard')
    return redirect('/accounts/settings/#system')
