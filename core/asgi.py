import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing

"""
ASGI config for IIA Management project.

This configures the ASGI application entrypoint, enabling support for WebSockets
and asynchronous routing via Django Channels alongside standard HTTP requests.
"""

# Establish default settings module reference
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Central ASGI application protocol router
application = ProtocolTypeRouter({
    # Standard Django HTTP request handler
    "http": get_asgi_application(),
    
    # Asynchronous WebSocket request handler, using AuthMiddlewareStack for session validation
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})
