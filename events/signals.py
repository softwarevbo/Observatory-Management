from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CalendarEvent
from tasks.calendar_sync import sync_event_to_google, sync_event_to_caldav, delete_from_external_calendars

"""
This module registers Signal Receivers that synchronize Calendar events
with Google Calendar and CalDAV (Radicale) servers upon database updates or deletions.
"""

@receiver(post_save, sender=CalendarEvent)
def handle_event_post_save(sender, instance, created, **kwargs):
    """
    Triggers calendar synchronization immediately after an event record is saved.
    Prevents recursion if the update only writes back synchronization ID parameters.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields:
        sync_fields = {'google_event_id', 'caldav_event_path'}
        if set(update_fields).issubset(sync_fields):
            return

    # Dispatch tasks to push sync updates
    sync_event_to_google(instance)
    sync_event_to_caldav(instance)


@receiver(post_delete, sender=CalendarEvent)
def handle_event_post_delete(sender, instance, **kwargs):
    """
    Removes events from Google Calendar and Radicale when deleted from the local database.
    """
    delete_from_external_calendars(instance)
