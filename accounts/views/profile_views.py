from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render

"""
This module handles user profile and settings views.
It includes:
1. Main Project Management Profile View with user task/project summaries.
2. Dynamic Base Template resolution depending on user permission levels (Telescope, Inventory, PM).
3. Settings interface for updating self profile metadata, reporting system issues, 
   changing email preferences, and saving system configurations (admin only).
4. Specialized Profile and Settings views for separate Inventory and Telescope portals.
"""

@login_required
def profile_view(request):
    """
    Renders the logged-in user's profile page based on their active portal/role.
    """
    u = request.user
    if hasattr(u, "_meta"):
        if u._meta.model_name == "telescopeuser":
            return redirect("accounts:telescope_profile")
        elif u._meta.model_name == "inventoryuser":
            return redirect("accounts:inventory_profile")

    from accounts.rbac import get_canonical_role, ROLE_TCS_ADMIN, ROLE_TCS_MEMBER
    role = get_canonical_role(u)
    referer = request.META.get('HTTP_REFERER', '')
    if role in [ROLE_TCS_ADMIN, ROLE_TCS_MEMBER] or 'telescope' in referer or 'telescopecontrol' in referer:
        return redirect("accounts:telescope_profile")

    from tasks.models import Project, Task

    # Query tasks where the user is an assignee
    my_tasks = Task.objects.filter(assignees=u)
    
    # Query projects where the user is listed as either a manager or a member.
    my_projects = Project.objects.filter(Q(managers=u) | Q(members=u)).distinct()
    
    # Calculate task status metrics
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
    """
    Return the correct base HTML layout template based on the user's primary access rights.
    """
    can_pm        = getattr(user, 'can_access_pm', True)
    can_telescope = getattr(user, 'can_access_telescope', False)
    can_inventory = getattr(user, 'can_access_inventory', False)

    if can_telescope and not can_pm:
        return "telescope/base.html"

    if can_inventory and not can_pm and not can_telescope:
        return "inventory_base.html"

    return "base.html"


@login_required
def settings_view(request):
    """
    Renders and handles the user settings panel.
    """
    u = request.user
    if hasattr(u, "_meta"):
        if u._meta.model_name == "telescopeuser":
            return redirect("accounts:telescope_settings")
        elif u._meta.model_name == "inventoryuser":
            return redirect("accounts:inventory_settings")

    from tasks.models import SystemIssue, SystemSettings
    from events.models import UserCalendarSettings

    # Ensure calendar settings model instance exists for the user
    UserCalendarSettings.objects.get_or_create(user=request.user)
    
    # Retrieve system settings singleton instance
    sys_settings = SystemSettings.get_settings()

    if request.method == "POST":
        action = request.POST.get("action")

        # ─── ACTION: Update Personal Profile ───
        if action == "update_profile":
            from accounts.models import User as UserModel
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
            
            new_email = request.POST.get("email", "").strip()
            if new_email and new_email != user.email:
                if UserModel.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                    messages.error(request, "That email address is already in use by another account.")
                    return redirect("/accounts/settings/#account")
                user.email = new_email
            elif not new_email:
                user.email = ""
            
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

        # ─── ACTION: Update User Preferences ───
        elif action == "update_preferences":
            user = request.user
            user.theme_preference = request.POST.get(
                "theme_preference", user.theme_preference
            )
            user.email_notifications = request.POST.get("email_notifications") == "on"
            user.save()
            messages.success(request, "Preferences updated successfully.")
            return redirect("/accounts/settings/#preferences")

        # ─── ACTION: Remote Session Logout ───
        elif action == "delete_session":
            from accounts.models import UserLoginHistory
            session_id = request.POST.get("session_id")
            if session_id:
                UserLoginHistory.objects.filter(pk=session_id).delete()
                messages.success(request, "Session logged out remotely.")
            return redirect("/accounts/settings/#login_history")

        # ─── ACTION: Report System Issue ───
        elif action == "report_issue":
            SystemIssue.objects.create(
                title=request.POST.get("title"),
                description=request.POST.get("description"),
                issue_type=request.POST.get("issue_type", "bug"),
                reported_by=request.user,
            )
            messages.success(request, "Thank you! Your issue has been reported.")
            return redirect("/accounts/settings/#issues")

        # ─── ACTION: Update System Settings (ROOT Admin Only) ───
        elif action == "update_system_settings" and (request.user.is_superuser or getattr(request.user, 'role', '') == 'ROOT'):
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
    from accounts.models import UserLoginHistory, get_client_ip
    files_settings = FileSystemSettings.objects.first()
    if not files_settings:
        files_settings = FileSystemSettings.objects.create()

    is_root = getattr(request.user, 'is_superuser', False) or getattr(request.user, 'role', '') == 'ROOT'

    if is_root:
        login_history = UserLoginHistory.objects.all().select_related("user")[:100]
    else:
        login_history = UserLoginHistory.objects.filter(user=request.user)[:50]

    if not login_history.exists():
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:255]
        UserLoginHistory.objects.create(
            user=request.user,
            ip_address=ip,
            user_agent=ua
        )
        if is_root:
            login_history = UserLoginHistory.objects.all().select_related("user")[:100]
        else:
            login_history = UserLoginHistory.objects.filter(user=request.user)[:50]

    return render(
        request,
        "accounts/settings.html",
        {
            "base_template": _resolve_base_template(request.user),
            "sys_settings": sys_settings,
            "files_settings": files_settings,
            "login_history": login_history,
            "reported_issues": (
                SystemIssue.objects.all().order_by("-created_at")
                if is_root
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


@login_required
def inventory_profile_view(request):
    """
    Renders separate profile detail cards for Inventory Users.
    Displays adjustment counts and rentals made by this specific staff member.
    """
    from inventory.models import InventoryAdjustment, Rental
    u = request.user
    stats = {
        "adjustments_count": InventoryAdjustment.objects.filter(created_by=u).count(),
        "rentals_count": Rental.objects.filter(created_by=u).count(),
    }
    return render(
        request,
        "accounts/inventory_profile.html",
        {
            "profile_user": u,
            "stats": stats,
        }
    )


@login_required
def inventory_settings_view(request):
    """
    Allows self-updates of email and password credentials for Inventory users.
    """
    u = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_profile":
            u.email = request.POST.get("email", u.email)
            new_pw = request.POST.get("new_password")
            if new_pw:
                u.set_password(new_pw)
                update_session_auth_hash(request, u)
            u.save()
            messages.success(request, "Inventory profile updated successfully.")
            return redirect("accounts:inventory_settings")
            
    return render(
        request,
        "accounts/inventory_settings.html",
        {
            "profile_user": u,
        }
    )


@login_required
def telescope_profile_view(request):
    """
    Renders profile statistics, self-service settings edit form, and authorization parameters for TCS users.
    Supports both standard User accounts and TelescopeUser model instances.
    """
    from telescope.models import Telescope, TelescopeUser
    from accounts.rbac import get_canonical_role, ROLE_ROOT, ROLE_TCS_ADMIN
    
    u = request.user
    role = get_canonical_role(u)
    is_tele_admin = u.is_superuser or getattr(u, 'is_root', False) or getattr(u, 'is_telescope_admin', False) or role in [ROLE_ROOT, ROLE_TCS_ADMIN]

    if request.method == "POST":
        action = request.POST.get("action", "update_profile")
        if action == "update_profile":
            first_name = request.POST.get("first_name", u.first_name).strip()
            last_name = request.POST.get("last_name", u.last_name).strip()
            email = request.POST.get("email", u.email).strip()
            phone = request.POST.get("phone", getattr(u, "phone", "")).strip()
            department = request.POST.get("department", getattr(u, "department", "astronomy")).strip()
            designation = request.POST.get("designation", getattr(u, "designation", "")).strip()
            theme_preference = request.POST.get("theme_preference", getattr(u, "theme_preference", "dark")).strip()
            avatar_color = request.POST.get("avatar_color", getattr(u, "avatar_color", "#4f8ef7")).strip()

            if hasattr(u, "first_name"): u.first_name = first_name
            if hasattr(u, "last_name"): u.last_name = last_name
            if hasattr(u, "email"): u.email = email
            if hasattr(u, "phone"): u.phone = phone
            if hasattr(u, "department"): u.department = department
            if hasattr(u, "designation"): u.designation = designation
            if hasattr(u, "theme_preference"): u.theme_preference = theme_preference
            if hasattr(u, "avatar_color"): u.avatar_color = avatar_color

            new_pw = request.POST.get("new_password", "").strip()
            if new_pw:
                u.set_password(new_pw)
                update_session_auth_hash(request, u)

            u.save()
            messages.success(request, "Your TCS user profile settings have been updated successfully.")
            return redirect("accounts:telescope_profile")

    if hasattr(u, 'get_accessible_telescopes'):
        telescopes = u.get_accessible_telescopes()
    elif hasattr(u, 'assigned_telescopes') and getattr(u, 'role', '') == 'observer' and not is_tele_admin:
        telescopes = u.assigned_telescopes.all()
    else:
        telescopes = Telescope.objects.all()

    accessible_codes = [t.code.lower() for t in telescopes] if telescopes else []

    department_choices = getattr(TelescopeUser, 'DEPARTMENT_CHOICES', [
        ('optics', 'Optics & Instrumentation'),
        ('electronics', 'Control Electronics'),
        ('software', 'Software & Telemetry'),
        ('astronomy', 'Observational Astronomy'),
        ('operations', 'Site Operations'),
    ])

    return render(
        request,
        "accounts/telescope_profile.html",
        {
            "profile_user": u,
            "user_obj": u,
            "is_tele_admin": is_tele_admin,
            "telescopes": telescopes,
            "accessible_codes": accessible_codes,
            "department_choices": department_choices,
        }
    )


@login_required
def telescope_settings_view(request):
    """
    Enables self profile updates and theme choice configurations for Telescope Operators.
    """
    u = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "update_profile":
            u.first_name = request.POST.get("first_name", u.first_name)
            u.last_name = request.POST.get("last_name", u.last_name)
            u.nickname = request.POST.get("nickname", u.nickname)
            u.designation = request.POST.get("designation", u.designation)
            u.phone = request.POST.get("phone", u.phone)
            
            if "profile_picture" in request.FILES:
                u.profile_picture = request.FILES["profile_picture"]
                
            if "avatar_color" in request.POST:
                u.avatar_color = request.POST.get("avatar_color")
                
            new_pw = request.POST.get("new_password")
            if new_pw:
                u.set_password(new_pw)
                update_session_auth_hash(request, u)
                
            u.save()
            messages.success(request, "Telescope control profile updated successfully.")
            return redirect("accounts:telescope_settings")
            
        elif action == "update_preferences":
            u.theme_preference = request.POST.get("theme_preference", u.theme_preference)
            u.save()
            messages.success(request, "Preferences updated successfully.")
            return redirect("accounts:telescope_settings")
            
    return render(
        request,
        "accounts/telescope_settings.html",
        {
            "profile_user": u,
        }
    )



