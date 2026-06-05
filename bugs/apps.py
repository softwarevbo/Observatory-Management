from django.apps import AppConfig

"""
This module defines configuration parameters for the bugs application.
"""

class BugsConfig(AppConfig):
    """
    AppConfig for the 'bugs' Django app.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "bugs"
