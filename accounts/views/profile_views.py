from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render


@login_required
def profile_view(request):
    from tasks.models import Project, Task

    u = request.user
    my_tasks = Task.objects.filter(assignees=u)
    my_projects = Project.objects.filter(Q(managers=u) | Q(members=u)).distinct()
    task_stats = {
        "total": my_tasks.count(),
        "todo": my_tasks.filter(status="todo").count(),
        "in_progress": my_tasks.filter(status="in_progress").count(),
        "done": my_tasks.filter(status="done").count(),
        "overdue": sum(1 for t in my_tasks if t.is_overdue),
    }
    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": u,
            "my_tasks": my_tasks[:8],
            "my_projects": my_projects[:6],
            "task_stats": task_stats,
        },
    )


def _resolve_base_template(user):
    """Return the correct base template based on the user's primary access rights.

    Priority rules:
    - Telescope-only users  → telescope/base.html
    - Inventory-only users  → inventory_base.html
    - PM / admin / members  → base.html  (Observatory Management)
    """
    can_pm        = getattr(user, 'can_access_pm', True)
    can_telescope = getattr(user, 'can_access_telescope', False)
    can_inventory = getattr(user, 'can_access_inventory', False)

    # Telescope console users who don't also have PM access
    if can_telescope and not can_pm:
        return "telescope/base.html"

    # Inventory-only users
    if can_inventory and not can_pm and not can_telescope:
        return "inventory_base.html"

    # Everyone else: observatory management workspace
    return "base.html"


@login_required
def settings_view(request):
    from tasks.models import SystemIssue, SystemSettings
    from events.models import UserCalendarSettings

    UserCalendarSettings.objects.get_or_create(user=request.user)
    sys_settings = SystemSettings.get_settings()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_profile":
            user = request.user
            (
                user.first_name,
                user.last_name,
                user.nickname,
                user.designation,
                user.phone,
            ) = (
                request.POST.get("first_name", user.first_name),
                request.POST.get("last_name", user.last_name),
                request.POST.get("nickname", user.nickname),
                request.POST.get("designation", user.designation),
                request.POST.get("phone", user.phone),
            )
            if "profile_picture" in request.FILES:
                user.profile_picture = request.FILES["profile_picture"]
            if "avatar_color" in request.POST:
                user.avatar_color = request.POST.get("avatar_color")
            if request.POST.get("new_password"):
                user.set_password(request.POST.get("new_password"))
                update_session_auth_hash(request, user)
            user.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("/accounts/settings/#account")

        elif action == "update_preferences":
            user = request.user
            user.theme_preference = request.POST.get(
                "theme_preference", user.theme_preference
            )
            user.email_notifications = request.POST.get("email_notifications") == "on"
            user.save()
            messages.success(request, "Preferences updated successfully.")
            return redirect("/accounts/settings/#preferences")

        elif action == "report_issue":
            SystemIssue.objects.create(
                title=request.POST.get("title"),
                description=request.POST.get("description"),
                issue_type=request.POST.get("issue_type", "bug"),
                reported_by=request.user,
            )
            messages.success(request, "Thank you! Your issue has been reported.")
            return redirect("/accounts/settings/#issues")

        elif action == "update_system_settings" and request.user.is_admin:
            (
                sys_settings.primary_color,
                sys_settings.font_size,
                sys_settings.default_pm_password,
            ) = (
                request.POST.get("primary_color", sys_settings.primary_color),
                request.POST.get("font_size", sys_settings.font_size),
                request.POST.get(
                    "default_pm_password", sys_settings.default_pm_password
                ),
            )
            sys_settings.save()

            from files.models import SystemSettings as FileSystemSettings
            files_settings = FileSystemSettings.objects.first()
            if not files_settings:
                files_settings = FileSystemSettings.objects.create()
            if "max_file_size_gb" in request.POST:
                try:
                    files_settings.max_file_size_gb = int(
                        request.POST.get("max_file_size_gb")
                    )
                    files_settings.save()
                except ValueError:
                    pass

            messages.success(request, "System settings updated successfully.")
            return redirect("/accounts/settings/#system")

    from files.models import SystemSettings as FileSystemSettings
    files_settings = FileSystemSettings.objects.first()
    if not files_settings:
        files_settings = FileSystemSettings.objects.create()

    return render(
        request,
        "accounts/settings.html",
        {
            "base_template": _resolve_base_template(request.user),
            "sys_settings": sys_settings,
            "files_settings": files_settings,
            "reported_issues": (
                SystemIssue.objects.all().order_by("-created_at")
                if request.user.is_admin
                else SystemIssue.objects.none()
            ),
            "my_issues": SystemIssue.objects.filter(
                reported_by=request.user
            ).order_by("-created_at"),
            "calendar_settings": UserCalendarSettings.objects.get_or_create(
                user=request.user
            )[0],
        },
    )
