from django.urls import path
from . import views

"""
This module defines URL routing configurations for the Events / Calendar application.
"""

app_name = "events"

urlpatterns = [
    # Main interactive calendar grid view page
    path("", views.calendar_view, name="calendar"),
    
    # Event CRUD actions
    path("event/create/", views.event_create, name="event_create"),
    path("event/<int:pk>/", views.event_detail, name="event_detail"),
    path("event/<int:pk>/edit/", views.event_edit, name="event_edit"),
    path("event/<int:pk>/delete/", views.event_delete, name="event_delete"),
    
    # Google OAuth handshake endpoints (currently stubbed/disabled in views)
    path("google-init/", views.google_calendar_init, name="google_calendar_init"),
    path("google-callback/", views.google_calendar_callback, name="google_calendar_callback"),
    
    # Toggle Radicale (CalDAV) sync setting action
    path("toggle-caldav/", views.toggle_caldav_sync, name="toggle_caldav_sync"),
]
