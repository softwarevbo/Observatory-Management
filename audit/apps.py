from django.apps import AppConfig

"""
This module defines the AppConfig class for the audit application.
Django uses this class to configure settings and hook lifecycle signals on startup.
"""

class AuditConfig(AppConfig):
    """
    Configuration class representing the 'audit' application.
    """
    # AutoField primary key configuration
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
