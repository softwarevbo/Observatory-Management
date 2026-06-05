from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from datetime import timedelta

from tasks.models import Project
from accounts.models import User
from .models import Notification

"""
This module processes views and controllers for checking and managing user notifications.
"""


@login_required
def notifications_list(request):
    """
    Renders user's notifications, supporting pagination and filters
    (by unread status, type, project, sender, and timeframe).
    Synchronizes repository invitation states for invite notification clicks.
    """
    notifs = Notification.objects.filter(recipient=request.user).select_related(
        "sender", "task", "project"
    )
    status_filter = request.GET.get("status", "unread")
    type_filter = request.GET.get("type", "")
    project_filter = request.GET.get("project_id", "")
    sender_filter = request.GET.get("sender_id", "")
    timeframe_filter = request.GET.get("timeframe", "")
    search_query = request.GET.get("q", "").strip()

    if request.GET.get("mark_all"):
        notifs.update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect("tasks:notifications")

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    if status_filter == "unread":
        notifs = notifs.filter(is_read=False)
    elif status_filter == "read":
        notifs = notifs.filter(is_read=True)

    if type_filter:
        notifs = notifs.filter(notification_type=type_filter)

    if project_filter:
        notifs = notifs.filter(project_id=project_filter)

    if sender_filter:
        notifs = notifs.filter(sender_id=sender_filter)

    if timeframe_filter:
        now = timezone.now()
        if timeframe_filter == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            notifs = notifs.filter(created_at__gte=start_date)
        elif timeframe_filter == "week":
            start_date = now - timedelta(days=7)
            notifs = notifs.filter(created_at__gte=start_date)
        elif timeframe_filter == "month":
            start_date = now - timedelta(days=30)
            notifs = notifs.filter(created_at__gte=start_date)

    if search_query:
        notifs = notifs.filter(
            models.Q(title__icontains=search_query) | models.Q(message__icontains=search_query)
        )

    if request.user.is_admin:
        user_projects = Project.objects.all()
    else:
        user_projects = Project.objects.filter(
            models.Q(managers=request.user) | models.Q(members=request.user)
        ).distinct()

    all_users = User.objects.exclude(id=request.user.id)

    paginator = Paginator(notifs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Map repository invitations to notifications of type repo_invite
    try:
        from resource_hub.models import RepoInvitation
        pending_invites = list(
            RepoInvitation.objects.filter(
                invitee=request.user, is_accepted=False
            ).select_related('repository')
        )
        pending_by_repo_name = {inv.repository.name.lower(): inv for inv in pending_invites}
    except Exception:
        pending_by_repo_name = {}

    for n in page_obj:
        if n.notification_type == 'repo_invite' and pending_by_repo_name:
            matched = None
            msg_lower = (n.message or '').lower()
            for repo_name_lower, inv in pending_by_repo_name.items():
                if repo_name_lower in msg_lower:
                    matched = inv
                    break
            # Do not fall back to an unrelated invitation if no matching repository invite is active
            n.repo_invite = matched
        else:
            n.repo_invite = None

    return render(
        request,
        "notifications/notifications.html",
        {
            "notifications": page_obj,
            "page_obj": page_obj,
            "unread_count": unread_count,
            "status_filter": status_filter,
            "type_filter": type_filter,
            "project_filter": project_filter,
            "sender_filter": sender_filter,
            "timeframe_filter": timeframe_filter,
            "search_query": search_query,
            "type_choices": Notification.TYPE_CHOICES,
            "user_projects": user_projects,
            "all_users": all_users,
        },
    )


@login_required
def notification_read(request, pk):
    """
    Marks a single notification as read and redirects the user to the corresponding action target
    (e.g., chat room, repository invitation list, task detail, or project page).
    """
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save()
    if notif.notification_type == 'chat_message':
        return redirect("chat:home")
    if notif.notification_type == 'repo_invite':
        return redirect("resource_hub:repo_list")
    if notif.task:
        return redirect("tasks:task_detail", pk=notif.task.pk)
    if notif.project:
        return redirect("tasks:project_detail", pk=notif.project.pk)
    return redirect("tasks:notifications")
