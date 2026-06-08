from django.apps import AppConfig
import os


class ResourceHubConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "resource_hub"

    def ready(self):
        # Set global Git parameters to bypass ownership checks for child processes
        os.environ['GIT_CONFIG_PARAMETERS'] = "'safe.directory=*'"
