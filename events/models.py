from django.conf import settings
from django.db import models

"""
This module defines database models for the Events application.
It stores milestone timelines, meeting schedules, locations, passwords,
and user-specific Radicale CalDAV/Google integration sync keys.
"""

class CalendarEvent(models.Model):
    """
    Model representing scheduled calendar events.
    """
    TYPE_CHOICES = [
        ("milestone", "Milestone"),
        ("meeting", "Meeting"),
        ("deadline", "Deadline"),
        ("review", "Review"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="other")
    
    # Optional references to project or specific task records
    project = models.ForeignKey(
        "tasks.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    task = models.ForeignKey(
        "tasks.Task", on_delete=models.SET_NULL, null=True, blank=True
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="calendar_events"
    )
    
    # Remote meeting linkage parameters
    meeting_link = models.URLField(max_length=500, blank=True, null=True)
    meeting_password = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=300, blank=True, null=True, help_text="Physical location or room")
    color = models.CharField(max_length=7, default="#6366f1")
    
    # Synchronization reference paths
    google_event_id = models.CharField(max_length=255, blank=True, null=True)
    caldav_event_path = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Maps database table structure to tasks namespace for historical migration compatibility
        db_table = "tasks_calendarevent"
        ordering = ["start_datetime"]

    def __str__(self):
        return self.title


class UserCalendarSettings(models.Model):
    """
    Model representing user integration settings for external calendar sync.
    Stores CalDAV URLs, Google OAuth JSON tokens, and synchronization flags.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_settings",
    )
    # CalDAV settings (e.g. Radicale server)
    caldav_url = models.URLField(max_length=500, default="http://localhost:5232/")
    caldav_user = models.CharField(
        max_length=100, default="your_username", blank=True, null=True
    )
    caldav_password = models.CharField(max_length=100, blank=True, null=True)
    caldav_calendar_name = models.CharField(max_length=100, default="IIAP OM")

    # Google Calendar credentials parameters
    google_calendar_id = models.CharField(max_length=255, default="primary")
    google_oauth_token = models.JSONField(blank=True, null=True) # Stores refresh/access tokens
    
    is_google_synced = models.BooleanField(default=False)
    is_caldav_synced = models.BooleanField(default=False)

    class Meta:
        # Maps database table structure to tasks namespace for historical migration compatibility
        db_table = "tasks_usercalendarsettings"

    def __str__(self):
        return f"Calendar Settings for {self.user.username}"
