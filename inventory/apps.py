from django.apps import AppConfig

"""
This module defines configuration parameters for the Inventory app.
Registers the post_save, post_delete, and pre_save signals during startup.
"""

class InventoryConfig(AppConfig):
    """AppConfig class for the inventory application."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"

    def ready(self):
        """Imports signals when the application is loaded to activate receivers."""
        import inventory.signals
