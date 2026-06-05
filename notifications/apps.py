from django.apps import AppConfig

"""
This module defines configuration settings for the Notifications application.
"""

class NotificationsConfig(AppConfig):
    """
    AppConfig class for the notifications application.
    Sets standard primary key auto field type.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
