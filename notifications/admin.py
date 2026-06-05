from django.contrib import admin
from .models import Notification

"""
This module registers the Notifications application models in the Django Admin portal.
"""

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Notification model.
    Organizes search indices, list filters, and display fields.
    """
    list_display = ["title", "recipient", "sender", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["title", "message"]
