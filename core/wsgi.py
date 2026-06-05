import os
from django.core.wsgi import get_wsgi_application

"""
WSGI config for IIA Management project.

This configures the WSGI application entrypoint for deployment on standard HTTP servers.
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

application = get_wsgi_application()
