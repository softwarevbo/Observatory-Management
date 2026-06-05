from django.apps import AppConfig

"""
This module defines the AppConfig class for the accounts application.
Django uses this configuration to configure and initialize the application when the project starts.
"""

class AccountsConfig(AppConfig):
    """
    Configuration class for the 'accounts' Django application.
    
    This class inherits from Django's AppConfig. It sets the database field type for
    automatically generated primary keys and references the package path name.
    """
    # Specifies the default primary key field type for model primary keys.
    # BigAutoField is a 64-bit integer that auto-increments (safe for large tables).
    default_auto_field = "django.db.models.BigAutoField"
    
    # The full python path to the application package.
    name = "accounts"
