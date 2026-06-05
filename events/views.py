import json
import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.conf import settings

from tasks.models import Project, Task, AuditLog
from tasks.decorators import admin_required
from tasks.services.notification_service import NotificationService
from tasks.utils.query_utils import get_visible_tasks_qs
from .models import CalendarEvent, UserCalendarSettings
from .forms import CalendarEventForm

"""
This module contains views for managing calendar operations, CRUD event actions,
and Radicale CalDAV synchronization adjustments.
"""

@login_required
def calendar_view(request):
    """
    Renders the FullCalendar grid page.
    Compiles calendar events and task deadlines/due dates to display on the calendar interface.
    """
    # Load calendar events where user is creator or listed as an attendee
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

    # Pull user's visible tasks with defined due dates or deadlines
    my_tasks = get_visible_tasks_qs(
        request.user,
        Task.objects.filter(
            Q(assignees=request.user) | Q(created_by=request.user),
            Q(due_date__isnull=False) | Q(deadline__isnull=False),
        )
    ).distinct()

    # Append tasks to calendar list
    for t in my_tasks:
        if t.due_date:
            events_data.append(
                {
                    "id": f"task-due-{t.pk}",
                    "title": f"Task Due: {t.title}",
                    "start": t.due_date.isoformat(),
                    "allDay": True,
                    "color": "#ef4444" if t.is_overdue else "#3b82f6", # Overdue tasks show as red
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
    """
    Renders and processes calendar event creation forms.
    Sends notifications to project members when a new event is scheduled.
    """
    form = CalendarEventForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.created_by = request.user
        event.save()
        form.save_m2m() # Saves attendees checkboxes list

        # If event is linked to a project, notify project managers and members
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
    """
    Modifies calendar event details. Restricted to event owner, PMs, and Admins.
    Sends update alerts to attendees.
    """
    event = get_object_or_404(CalendarEvent, pk=pk)
    
    # Permission check: creator, PM, or Admin
    if event.created_by != request.user and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "You do not have permission to edit this event.")
        return redirect("tasks:calendar")

    form = CalendarEventForm(request.POST or None, instance=event, user=request.user)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        
        # Notify event attendees
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
    """
    Renders detailed information page of a single calendar event.
    """
    event = get_object_or_404(CalendarEvent, pk=pk)
    can_edit = event.created_by == request.user or request.user.is_admin or request.user.is_project_manager
    return render(
        request,
        "calendar/event_detail.html",
        {"event": event, "can_edit": can_edit}
    )


@login_required
def event_delete(request, pk):
    """
    Deletes calendar events. Restricted to event owners, PMs, and Admins.
    """
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


# ─── GOOGLE CALENDAR SYNC (DISABLED) ───

@login_required
@admin_required
def google_calendar_init(request):
    """Placeholder: Google Calendar Sync is currently deactivated."""
    messages.error(request, "Google Calendar integration is disabled.")
    return redirect("accounts:settings")


@login_required
@admin_required
def google_calendar_callback(request):
    """Placeholder: Google Calendar Sync callback handler."""
    messages.error(request, "Google Calendar integration is disabled.")
    return redirect("accounts:settings")


# ─── CALDAV SYNC (RADICALE) ───

@login_required
@admin_required
def toggle_caldav_sync(request):
    """
    Toggles Radicale CalDAV calendar synchronization options and logs actions to system audit logs.
    """
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

        # Write audit log entry tracking connection changes
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
