from django.urls import re_path
from . import consumers

"""
This module defines WebSocket URL routing patterns for Django Channels.
It maps incoming WebSocket path requests to their respective ASGI consumers.
"""

websocket_urlpatterns = [
    # Route for active chat room socket connections (direct, group, or project)
    re_path(r'^ws/chat/(?P<room_id>[^/]+)/?$', consumers.ChatConsumer.as_asgi()),
    
    # Route for system notifications socket connections
    re_path(r'^ws/notifications/?$', consumers.NotificationConsumer.as_asgi()),
    
    # Wildcard catch-all fallback route to reject unmapped socket requests gracefully
    re_path(r'^.*$', consumers.DummyConsumer.as_asgi()),
]
