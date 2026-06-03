import json
import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.conf import settings
from google_auth_oauthlib.flow import Flow

from tasks.models import Project, Task, AuditLog
from tasks.decorators import admin_required
from tasks.services.notification_service import NotificationService
from .models import CalendarEvent, UserCalendarSettings
from .forms import CalendarEventForm


@login_required
def calendar_view(request):
    events = CalendarEvent.objects.filter(
        Q(created_by=request.user) | Q(attendees=request.user)
    ).distinct()
    events_data = [
        {
            "id": e.pk,
            "title": e.title,
            "start": e.start_datetime.isoformat(),
            "end": e.end_datetime.isoformat(),
            "color": e.color,
            "url": f"/calendar/event/{e.pk}/",
            "meeting_link": e.meeting_link,
            "meeting_password": e.meeting_password,
        }
        for e in events
    ]

    my_tasks = Task.objects.filter(
        Q(assignees=request.user) | Q(created_by=request.user),
        Q(due_date__isnull=False) | Q(deadline__isnull=False),
    ).distinct()

    for t in my_tasks:
        if t.due_date:
            events_data.append(
                {
                    "id": f"task-due-{t.pk}",
                    "title": f"Task Due: {t.title}",
                    "start": t.due_date.isoformat(),
                    "allDay": True,
                    "color": "#ef4444" if t.is_overdue else "#3b82f6",
                    "url": f"/tasks/{t.pk}/",
                }
            )
        if t.deadline:
            events_data.append(
                {
                    "id": f"task-deadline-{t.pk}",
                    "title": f"Task Deadline: {t.title}",
                    "start": t.deadline.isoformat(),
                    "allDay": True,
                    "color": "#9333ea",
                    "url": f"/tasks/{t.pk}/",
                }
            )

    upcoming_tasks = my_tasks.order_by("due_date")[:5]

    return render(
        request,
        "calendar/calendar.html",
        {
            "events_json": json.dumps(events_data),
            "events": events.order_by("start_datetime")[:10],
            "upcoming_tasks": upcoming_tasks,
            "form": CalendarEventForm(),
        },
    )


@login_required
def event_create(request):
    form = CalendarEventForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.created_by = request.user
        event.save()
        form.save_m2m()

        if event.project:
            members = set(event.project.members.all()) | set(
                event.project.managers.all()
            )
            for member in members:
                if member != request.user:
                    msg = f"A new event '{event.title}' has been scheduled for project {event.project.name}."
                    if event.meeting_link:
                        msg += f" Meeting Link: {event.meeting_link}"
                        if event.meeting_password:
                            msg += f" (Password: {event.meeting_password})"

                    NotificationService.create_notification(
                        member,
                        request.user,
                        "project_update",
                        f"New Project Event: {event.title}",
                        msg,
                        project=event.project,
                    )

        messages.success(request, f'Event "{event.title}" created.')
        return redirect("tasks:calendar")

    return render(
        request,
        "calendar/event_form.html",
        {"form": form, "title": "Create New Event", "action": "Create Event"},
    )


@login_required
def event_edit(request, pk):
    event = get_object_or_404(CalendarEvent, pk=pk)
    if event.created_by != request.user and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "You do not have permission to edit this event.")
        return redirect("tasks:calendar")

    form = CalendarEventForm(request.POST or None, instance=event, user=request.user)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        for attendee in event.attendees.all():
            if attendee != request.user:
                NotificationService.create_notification(
                    attendee,
                    request.user,
                    "project_update",
                    f"Event Updated: {event.title}",
                    f"The event '{event.title}' has been updated.",
                    project=event.project,
                )
        messages.success(request, f'Event "{event.title}" updated.')
        return redirect("tasks:calendar")

    return render(
        request,
        "calendar/event_form.html",
        {
            "form": form,
            "title": f"Edit Event: {event.title}",
            "action": "Save Changes",
            "event": event,
        },
    )


@login_required
def event_detail(request, pk):
    event = get_object_or_404(CalendarEvent, pk=pk)
    can_edit = event.created_by == request.user or request.user.is_admin or request.user.is_project_manager
    return render(
        request,
        "calendar/event_detail.html",
        {"event": event, "can_edit": can_edit}
    )


@login_required
def event_delete(request, pk):
    event = get_object_or_404(CalendarEvent, pk=pk)
    if event.created_by != request.user and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "You do not have permission to delete this event.")
        return redirect("tasks:calendar")

    if request.method == "POST":
        title = event.title
        event.delete()
        messages.success(request, f'Event "{title}" has been deleted.')
        return redirect("tasks:calendar")

    return render(
        request, "calendar/event_confirm_delete.html", {"event": event}
    )


# ─── GOOGLE CALENDAR OAUTH ───────────────────────────────────────────────────

CLIENT_SECRETS_FILE = os.path.join(settings.BASE_DIR, "client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@login_required
@admin_required
def google_calendar_init(request):
    """Start Google OAuth flow."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=request.build_absolute_uri(
            reverse("tasks:google_calendar_callback")
        ),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    request.session["google_oauth_state"] = state
    return redirect(authorization_url)


@login_required
@admin_required
def google_calendar_callback(request):
    """Handle Google OAuth callback."""
    state = request.session.get("google_oauth_state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=request.build_absolute_uri(
            reverse("tasks:google_calendar_callback")
        ),
    )

    flow.fetch_token(
        authorization_response=request.build_absolute_uri(request.get_full_path())
    )
    credentials = flow.credentials

    user_settings, _ = UserCalendarSettings.objects.get_or_create(user=request.user)
    user_settings.google_oauth_token = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    user_settings.is_google_synced = True
    user_settings.save()

    messages.success(request, "Google Calendar connected successfully!")
    return redirect("accounts:settings")


@login_required
@admin_required
def toggle_caldav_sync(request):
    """Toggle Radicale sync."""
    user_settings, _ = UserCalendarSettings.objects.get_or_create(user=request.user)
    if request.method == "POST":
        old_synced = user_settings.is_caldav_synced
        user_settings.caldav_url = request.POST.get(
            "caldav_url", user_settings.caldav_url
        )
        user_settings.caldav_user = request.POST.get(
            "caldav_user", user_settings.caldav_user
        )
        user_settings.caldav_password = request.POST.get(
            "caldav_password", user_settings.caldav_password
        )
        user_settings.is_caldav_synced = request.POST.get("is_caldav_synced") == "on"
        user_settings.save()

        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action_type="update",
            module="system",
            entity_name="Calendar Settings",
            details=f"CalDAV sync {'enabled' if user_settings.is_caldav_synced else 'disabled'} "
                    f"(was {'enabled' if old_synced else 'disabled'}). "
                    f"Server: {user_settings.caldav_url}",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        messages.success(request, "CalDAV settings updated.")
    return redirect("accounts:settings")
