from django.contrib import admin
from .models import CalendarEvent, UserCalendarSettings


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ["title", "event_type", "start_datetime", "end_datetime", "created_by"]
    list_filter = ["event_type", "project"]
    search_fields = ["title", "description"]


@admin.register(UserCalendarSettings)
class UserCalendarSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "caldav_url", "is_google_synced", "is_caldav_synced"]
