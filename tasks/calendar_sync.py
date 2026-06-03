import json
import logging
from datetime import datetime

import caldav
from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from icalendar import Calendar, Event

from events.models import CalendarEvent, UserCalendarSettings

logger = logging.getLogger(__name__)


def get_google_service(user_settings):
    """Get Google Calendar service for a user."""
    if not user_settings.google_oauth_token:
        return None

    creds = Credentials.from_authorized_user_info(
        user_settings.google_oauth_token,
        ["https://www.googleapis.com/auth/calendar.events"],
    )
    return build("calendar", "v3", credentials=creds)


def sync_event_to_google(event):
    """Sync a Django CalendarEvent to Google Calendar."""
    user_settings = UserCalendarSettings.objects.filter(user=event.created_by).first()
    if not user_settings or not user_settings.is_google_synced:
        print(
            f"[Sync] Creator {event.created_by} has no Google sync enabled. Falling back to Admin settings..."
        )
        from accounts.models import User

        admin_user = User.objects.filter(role="admin").first()
        if admin_user:
            user_settings = UserCalendarSettings.objects.filter(user=admin_user).first()

    if not user_settings or not user_settings.is_google_synced:
        return

    service = get_google_service(user_settings)
    if not service:
        return

    body = {
        "summary": event.title,
        "description": event.description,
        "start": {"dateTime": event.start_datetime.isoformat()},
        "end": {"dateTime": event.end_datetime.isoformat()},
        "location": event.meeting_link or "",
    }

    try:
        if event.google_event_id:
            service.events().update(
                calendarId=user_settings.google_calendar_id,
                eventId=event.google_event_id,
                body=body,
            ).execute()
        else:
            res = (
                service.events()
                .insert(calendarId=user_settings.google_calendar_id, body=body)
                .execute()
            )
            event.google_event_id = res["id"]
            event.save(update_fields=["google_event_id"])
    except Exception as e:
        logger.error(f"Error syncing to Google Calendar: {e}")


def sync_event_to_caldav(event):
    """Sync a Django CalendarEvent to CalDAV (Radicale)."""
    print(f"[Sync] Starting CalDAV sync for event: {event.title}")

    # Try to get settings for the creator first, then fallback to the admin
    user_settings = UserCalendarSettings.objects.filter(user=event.created_by).first()
    if not user_settings or not user_settings.is_caldav_synced:
        print(
            f"[Sync] Creator {event.created_by} has no sync enabled. Falling back to Admin settings..."
        )
        from accounts.models import User

        admin_user = User.objects.filter(role="admin").first()
        if admin_user:
            user_settings = UserCalendarSettings.objects.filter(user=admin_user).first()

    if not user_settings:
        print("[Sync] No calendar settings found (neither creator nor admin).")
        return

    if not user_settings.is_caldav_synced:
        print("[Sync] CalDAV sync is disabled globally (Admin settings).")
        return

    try:
        print(
            f"[Sync] Connecting to {user_settings.caldav_url} as {user_settings.caldav_user}"
        )
        client = caldav.DAVClient(
            url=user_settings.caldav_url,
            username=user_settings.caldav_user,
            password=user_settings.caldav_password,
        )
        principal = client.principal()
        calendars = principal.calendars()

        # Find or create the IIAP OM calendar
        target_cal = None
        for cal in calendars:
            # Check display name or URL part
            props = cal.get_properties([caldav.elements.dav.DisplayName()])
            display_name = props.get("{DAV:}displayname", "")
            if (
                display_name == user_settings.caldav_calendar_name
                or user_settings.caldav_calendar_name in str(cal.url)
            ):
                target_cal = cal
                break

        if not target_cal:
            print(f"[Sync] Creating new calendar: {user_settings.caldav_calendar_name}")
            target_cal = principal.make_calendar(
                name=user_settings.caldav_calendar_name
            )
        else:
            print(f"[Sync] Found existing calendar: {target_cal.url}")

        # Create iCalendar event
        ical = Calendar()
        ical.add("prodid", "-//IIAP OM Calendar//mxm.dk//")
        ical.add("version", "2.0")

        ical_event = Event()
        ical_event.add("summary", event.title)
        ical_event.add("description", event.description or "")
        ical_event.add("dtstart", event.start_datetime)
        ical_event.add("dtend", event.end_datetime)
        ical_event.add("dtstamp", datetime.now())
        ical_event.add("uid", f"iiap-pm-{event.pk}")
        ical_event.add("location", event.meeting_link or "")

        ical.add_component(ical_event)
        ical_data = ical.to_ical().decode("utf-8")

        if event.caldav_event_path:
            try:
                print(
                    f"[Sync] Updating existing remote event: {event.caldav_event_path}"
                )
                remote_event = target_cal.event_by_url(event.caldav_event_path)
                remote_event.data = ical_data
                remote_event.save()
            except Exception as e:
                print(f"[Sync] Update failed, trying to recreate: {e}")
                new_event = target_cal.save_event(ical_data)
                event.caldav_event_path = str(new_event.url)
                event.save(update_fields=["caldav_event_path"])
        else:
            print("[Sync] Saving new event to Radicale...")
            new_event = target_cal.save_event(ical_data)
            event.caldav_event_path = str(new_event.url)
            event.save(update_fields=["caldav_event_path"])
            print(f"[Sync] Successfully saved. Path: {event.caldav_event_path}")

    except Exception as e:
        print(f"[Sync] ERROR: {e}")
        logger.error(f"Error syncing to CalDAV: {e}")


def delete_from_external_calendars(event):
    """Delete event from Google and CalDAV."""
    print(f"[Sync] Deleting external event: {event.title}")

    # Delete from Google
    google_settings = UserCalendarSettings.objects.filter(user=event.created_by).first()
    if not google_settings or not google_settings.is_google_synced:
        from accounts.models import User

        admin_user = User.objects.filter(role="admin").first()
        if admin_user:
            google_settings = UserCalendarSettings.objects.filter(
                user=admin_user
            ).first()

    if google_settings and google_settings.is_google_synced and event.google_event_id:
        try:
            service = get_google_service(google_settings)
            if service:
                service.events().delete(
                    calendarId=google_settings.google_calendar_id,
                    eventId=event.google_event_id,
                ).execute()
                print("[Sync] Deleted from Google Calendar.")
        except Exception as e:
            logger.error(f"Error deleting from Google Calendar: {e}")

    # Delete from CalDAV
    caldav_settings = UserCalendarSettings.objects.filter(user=event.created_by).first()
    if not caldav_settings or not caldav_settings.is_caldav_synced:
        from accounts.models import User

        admin_user = User.objects.filter(role="admin").first()
        if admin_user:
            caldav_settings = UserCalendarSettings.objects.filter(
                user=admin_user
            ).first()

    if caldav_settings and caldav_settings.is_caldav_synced and event.caldav_event_path:
        try:
            client = caldav.DAVClient(
                url=caldav_settings.caldav_url,
                username=caldav_settings.caldav_user,
                password=caldav_settings.caldav_password,
            )
            # Principal and calendar discovery to find the correct calendar object
            principal = client.principal()
            calendars = principal.calendars()

            # Extract path from URL to match event_by_url behavior
            event_url = event.caldav_event_path

            # Find the calendar that contains this event
            found = False
            for cal in calendars:
                try:
                    remote_event = cal.event_by_url(event_url)
                    remote_event.delete()
                    print(f"[Sync] Deleted from CalDAV: {event_url}")
                    found = True
                    break
                except:
                    continue

            if not found:
                print(f"[Sync] Could not find event to delete on CalDAV: {event_url}")

        except Exception as e:
            print(f"[Sync] Delete ERROR: {e}")
            logger.error(f"Error deleting from CalDAV: {e}")
