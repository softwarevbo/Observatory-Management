from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.conf import settings
import os

from accounts.models import User
from ..models import Project, Task
from bugs.models import BugReport
from notifications.models import Notification
from ..utils.query_utils import get_visible_tasks_qs


@login_required
def dashboard(request):
    user = request.user
    today = timezone.now().date()

    if user.is_admin:
        db_size = 0
        db_path = settings.DATABASES["default"].get("NAME")
        if db_path and os.path.exists(db_path):
            db_size = os.path.getsize(db_path) / (1024 * 1024)

        from resource_hub.models import Repository
        from testcases.models import TestCase
        from tasks.models import AuditLog

        projects = Project.objects.all()
        active_projects_count = projects.exclude(
            status__in=["completed", "cancelled"]
        ).count()

        stats = {
            "total_projects": projects.count(),
            "active_projects": active_projects_count,
            "total_users": User.objects.count(),
            "db_size_mb": f"{db_size:.2f}",
            "deletion_reqs": projects.filter(
                Q(deletion_requested_by_admin=True) | Q(deletion_requested_by_pm=True)
            )
            .exclude(deletion_requested_by_admin=True, deletion_requested_by_pm=True)
            .count(),
            "total_repos": Repository.objects.count(),
            "total_test_cases": TestCase.objects.count(),
            "total_bugs": BugReport.objects.count(),
            "active_bugs": BugReport.objects.exclude(status__in=["resolved", "closed", "wont_fix"]).count(),
        }
        
        recent_logs = AuditLog.objects.select_related("user").order_by("-timestamp")[:6]
        
        return render(
            request,
            "tasks/admin_dashboard.html",
            {
                "stats": stats,
                "projects": projects.order_by("-updated_at")[:6],
                "recent_logs": recent_logs,
            },
        )

    # For PM and regular users
    if user.is_project_manager:
        projects = Project.objects.filter(
            Q(managers=user) | Q(members=user) | Q(project_incharge=user),
            is_archived=False
        ).distinct()
    else:
        projects = Project.objects.filter(members=user, is_archived=False).distinct()

    all_visible_tasks = get_visible_tasks_qs(user, Task.objects.filter(project__is_archived=False)).exclude(linked_bugs__is_in_trash=True)
    my_open_tasks_qs = all_visible_tasks.filter(assignees=user).exclude(status="done")

    overdue_tasks_list = [
        t for t in my_open_tasks_qs if t.due_date and t.due_date < today
    ]
    due_today_list = [t for t in my_open_tasks_qs if t.due_date == today]

    my_open_bugs_count = (
        BugReport.objects.filter(assignees=user, is_in_trash=False)
        .exclude(status__in=["resolved", "closed", "wont_fix"])
        .count()
    )

    my_bugs_display = (
        BugReport.objects.filter(Q(assignees=user) | Q(reported_by=user), is_in_trash=False)
        .exclude(status__in=["resolved", "closed", "wont_fix"])
        .distinct()[:5]
    )

    notifications = Notification.objects.filter(recipient=user, is_read=False)[:5]

    stats = {
        "total_projects": projects.count(),
        "active_projects": projects.exclude(
            status__in=["completed", "cancelled"]
        ).count(),
        "total_tasks": all_visible_tasks.count(),
        "my_open_tasks": my_open_tasks_qs.count(),
        "overdue_count": len(overdue_tasks_list),
        "completed_tasks": all_visible_tasks.filter(status="done").count(),
        "my_open_bugs": my_open_bugs_count,
    }

    context = {
        "stats": stats,
        "recent_tasks": all_visible_tasks.order_by("-updated_at")[:8],
        "overdue_tasks": overdue_tasks_list[:5],
        "due_today": due_today_list,
        "notifications": notifications,
        "projects": projects.order_by("-updated_at")[:6],
        "my_bugs": my_bugs_display,
    }
    return render(request, "tasks/dashboard.html", context)
