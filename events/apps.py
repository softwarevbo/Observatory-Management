from django.apps import AppConfig

"""
This module defines configuration parameters for the Events application.
It automatically registers events signal listeners on ready.
"""

class EventsConfig(AppConfig):
    """
    AppConfig for the 'events' Django app.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """
        Runs when Django finishes registry loading.
        Imports signals to connect receiver hooks.
        """
        import events.signals
