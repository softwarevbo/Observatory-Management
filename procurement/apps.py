from django.apps import AppConfig

"""
This module defines configuration settings for the Procurement application.
"""

class ProcurementConfig(AppConfig):
    """
    AppConfig class for the procurement application.
    Sets standard primary key auto field type.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "procurement"
