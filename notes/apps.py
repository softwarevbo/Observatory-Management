from django.apps import AppConfig

"""
This module defines configuration settings for the Notes application.
"""

class NotesConfig(AppConfig):
    """
    AppConfig class for the notes application.
    Sets standard primary key auto field type.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "notes"
