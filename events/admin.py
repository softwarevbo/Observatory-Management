from django.contrib import admin
from .models import CalendarEvent, UserCalendarSettings

"""
This module registers Calendar Event models with the Django Admin panel.
"""

@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """Admin configuration settings for the CalendarEvent model."""
    list_display = ["title", "event_type", "start_datetime", "end_datetime", "created_by"]
    list_filter = ["event_type", "project"]
    search_fields = ["title", "description"]


@admin.register(UserCalendarSettings)
class UserCalendarSettingsAdmin(admin.ModelAdmin):
    """Admin configuration settings for user-specific calendar connection profiles."""
    list_display = ["user", "caldav_url", "is_google_synced", "is_caldav_synced"]
