from django.apps import AppConfig

"""
This module defines configuration parameters for the Finance app.
"""

class FinanceConfig(AppConfig):
    """AppConfig class for the finance application."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "finance"
