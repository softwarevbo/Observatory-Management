from django.apps import AppConfig

"""
This module defines the configuration class for the Chat application.
It hooks the signal receivers on ready.
"""

class ChatConfig(AppConfig):
    """
    AppConfig for the 'chat' Django app.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        """
        Runs when Django finishes initializing the application registry.
        Imports signals to register receivers.
        """
        import chat.signals
