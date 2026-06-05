from django.contrib import admin

from .models import AuditLog

"""
This module registers the AuditLog model with Django's default administrative panel.
This allows administrators to browse, filter, search, and view audit history entries easily.
"""

# Registers AuditLog model to enable default administration management view
admin.site.register(AuditLog)
