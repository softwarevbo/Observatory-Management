from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CalendarEvent
from tasks.calendar_sync import sync_event_to_google, sync_event_to_caldav, delete_from_external_calendars

@receiver(post_save, sender=CalendarEvent)
def handle_event_post_save(sender, instance, created, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields:
        # Prevent recursion if the save was only to write sync IDs
        sync_fields = {'google_event_id', 'caldav_event_path'}
        if set(update_fields).issubset(sync_fields):
            return

    # Trigger synchronization
    sync_event_to_google(instance)
    sync_event_to_caldav(instance)

@receiver(post_delete, sender=CalendarEvent)
def handle_event_post_delete(sender, instance, **kwargs):
    delete_from_external_calendars(instance)
