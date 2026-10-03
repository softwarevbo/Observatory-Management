from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import AdminPasswordResetForm, UserCreateForm, UserEditForm
from ..models import User
from ..rbac import (
    can_assign_role,
    can_manage_target_user,
    can_manage_user_list,
    get_assignable_roles,
    get_canonical_role,
    get_default_redirect_for_role,
    has_permission,
    PERMISSION_ADMIN_MANAGE,
    PERMISSION_INVENTORY_USER_MANAGE,
    PERMISSION_PROJECT_USER_MANAGE,
    PERMISSION_TELESCOPE_USER_MANAGE,
    ROLE_IM_ADMIN,
    ROLE_IM_MEMBER,
    ROLE_PM_ADMIN,
    ROLE_PM_MEMBER,
    ROLE_ROOT,
    ROLE_TCS_ADMIN,
    ROLE_TCS_MEMBER,
    ROLE_TM_ADMIN,
    ROLE_TM_MEMBER,
)

"""
User Administration and Management Views.
Strictly separates access and management by module:
- ROOT: Can manage all tabs, admins, and members across modules.
- PM_ADMIN: Can access PM user tab only; manage PM_MEMBER users only.
- TM_ADMIN: Can access Telescope user tab only; manage TM_MEMBER users only.
- IM_ADMIN: Can access Inventory user tab only; manage IM_MEMBER users only.
- Members: Access Denied.
"""


@login_required
def user_list(request):
    """
    Lists users partitioned into tabs for Project Management, Inventory, and Telescope.
    Restricted by module administrator permissions.
    """
    canonical_role = get_canonical_role(request.user)

    if canonical_role == ROLE_PM_ADMIN:
        return user_list_pm(request)
    elif canonical_role in [ROLE_TCS_ADMIN, ROLE_TM_ADMIN]:
        return redirect("telescope:user_list")
    elif canonical_role == ROLE_IM_ADMIN:
        return user_list_inventory(request)

    active_tab = request.GET.get("tab", "pm")
    if active_tab == "telescope":
        return redirect("telescope:user_list")
    elif active_tab == "inventory":
        return user_list_inventory(request)

    return user_list_pm(request)


@login_required
def user_list_pm(request):
    """
    Project Management User Management Page.
    Lists PM users using Project Management layout (base.html).
    """
    if not (has_permission(request.user, PERMISSION_PROJECT_USER_MANAGE) or can_manage_user_list(request.user, "pm")):
        messages.error(request, "Access Denied: You do not have permission to view Project Management users.")
        return redirect(get_default_redirect_for_role(request.user))

    search = request.GET.get("q", "")
    role_filter = request.GET.get("role", "")
    team_filter = request.GET.get("team", "")
    status_filter = request.GET.get("status", "")

    users = User.objects.filter(can_access_pm=True).order_by("-date_joined")

    if search:
        users = users.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(designation__icontains=search)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    if team_filter:
        users = users.filter(team=team_filter)
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    stats = {
        "total": User.objects.filter(can_access_pm=True).count(),
        "active": User.objects.filter(can_access_pm=True, is_active=True).count(),
        "inactive": User.objects.filter(can_access_pm=True, is_active=False).count(),
        "admins": User.objects.filter(can_access_pm=True, role="PM_ADMIN").count() + User.objects.filter(can_access_pm=True, role="ROOT").count(),
        "managers": User.objects.filter(can_access_pm=True, role="PM_ADMIN").count(),
        "members": User.objects.filter(can_access_pm=True, role="PM_MEMBER").count(),
    }

    page_obj = Paginator(users, 10).get_page(request.GET.get("page"))

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "stats": stats,
            "search": search,
            "role_filter": role_filter,
            "team_filter": team_filter,
            "status_filter": status_filter,
            "role_choices": User.ROLE_CHOICES,
            "team_choices": User.MODULE_CHOICES,
            "active_tab": "pm",
            "assignable_roles": get_assignable_roles(request.user),
        },
    )


@login_required
def user_list_telescope(request):
    """
    Telescope Control User Management Page.
    Lists Telescope operators using Telescope layout (telescope/base.html).
    Querying dedicated TelescopeUser database table.
    """
    from telescope.models import TelescopeUser

    if not (has_permission(request.user, PERMISSION_TELESCOPE_USER_MANAGE) or can_manage_user_list(request.user, "telescope")):
        messages.error(request, "Access Denied: You do not have permission to view Telescope Control users.")
        return redirect(get_default_redirect_for_role(request.user))

    search = request.GET.get("q", "")
    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")

    users_tele = list(TelescopeUser.objects.all().order_by("-created_at"))
    users_auth = list(User.objects.filter(can_access_telescope=True).order_by("-date_joined"))
    users = users_tele + [u for u in users_auth if u.username not in [t.username for t in users_tele]]

    if search:
        users = [u for u in users if search.lower() in u.username.lower() or (getattr(u, "email", "") and search.lower() in u.email.lower())]
    if status_filter == "active":
        users = [u for u in users if u.is_active]
    elif status_filter == "inactive":
        users = [u for u in users if not u.is_active]

    stats = {
        "total": len(users),
        "active": len([u for u in users if u.is_active]),
        "inactive": len([u for u in users if not u.is_active]),
        "vbt_operators": len([u for u in users if getattr(u, "can_operate_vbt", False)]),
        "jcbt_operators": len([u for u in users if getattr(u, "can_operate_jcbt", False)]),
    }

    page_obj = Paginator(users, 10).get_page(request.GET.get("page"))

    return render(
        request,
        "telescope/user_list.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "stats": stats,
            "search": search,
            "role_filter": role_filter,
            "status_filter": status_filter,
            "assignable_roles": get_assignable_roles(request.user),
        },
    )


@login_required
def user_list_inventory(request):
    """
    Inventory Management User Management Page.
    Lists Inventory staff using Inventory layout (inventory_base.html).
    """
    from inventory.models import Branch, InventoryUser

    if not (has_permission(request.user, PERMISSION_INVENTORY_USER_MANAGE) or can_manage_user_list(request.user, "inventory")):
        messages.error(request, "Access Denied: You do not have permission to view Inventory Management users.")
        return redirect(get_default_redirect_for_role(request.user))

    search = request.GET.get("q", "")
    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")

    users = InventoryUser.objects.all().order_by("-created_at")

    if search:
        users = users.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    stats = {
        "total": InventoryUser.objects.count(),
        "active": InventoryUser.objects.filter(is_active=True).count(),
        "inactive": InventoryUser.objects.filter(is_active=False).count(),
        "super_admins": InventoryUser.objects.filter(role="super_admin").count(),
        "branch_admins": InventoryUser.objects.filter(role="branch_admin").count(),
        "staff": InventoryUser.objects.filter(role="staff").count(),
    }

    page_obj = Paginator(users, 10).get_page(request.GET.get("page"))

    return render(
        request,
        "inventory/user_list.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "stats": stats,
            "search": search,
            "role_filter": role_filter,
            "status_filter": status_filter,
            "branches": Branch.objects.all(),
            "assignable_roles": get_assignable_roles(request.user),
        },
    )


@login_required
def pm_user_profile(request, pk=None):
    """
    Renders Project Management profile page (base.html).
    """
    from tasks.models import Project, Task

    if pk:
        profile_user = get_object_or_404(User, pk=pk)
        if not can_manage_target_user(request.user, profile_user) and profile_user != request.user:
            messages.error(request, "Access Denied: You do not have permission to view this profile.")
            return redirect(get_default_redirect_for_role(request.user))
    else:
        profile_user = request.user

    assigned_tasks = Task.objects.filter(assignees=profile_user).select_related("project")
    task_stats = {
        "total": assigned_tasks.count(),
        "todo": assigned_tasks.filter(status="todo").count(),
        "in_progress": assigned_tasks.filter(status="in_progress").count(),
        "done": assigned_tasks.filter(status="done").count(),
        "overdue": sum(1 for t in assigned_tasks if t.is_overdue),
    }

    return render(
        request,
        "accounts/user_detail.html",
        {
            "profile_user": profile_user,
            "assigned_tasks": assigned_tasks[:10],
            "managed_projects": Project.objects.filter(managers=profile_user),
            "member_projects": Project.objects.filter(members=profile_user),
            "task_stats": task_stats,
        },
    )


@login_required
def telescope_user_profile(request, pk=None):
    """
    Renders Telescope Operator profile page (telescope/base.html).
    """
    if pk:
        profile_user = get_object_or_404(User, pk=pk)
        if not can_manage_target_user(request.user, profile_user) and profile_user != request.user:
            messages.error(request, "Access Denied: You do not have permission to view this operator profile.")
            return redirect(get_default_redirect_for_role(request.user))
    else:
        profile_user = request.user

    from telescope.models import Telescope
    telescopes = Telescope.objects.all()

    return render(
        request,
        "telescope/user_detail.html",
        {
            "profile_user": profile_user,
            "telescopes": telescopes,
            "is_tele_admin": profile_user.is_superuser or getattr(profile_user, "is_telescope_admin", False),
        },
    )


@login_required
def inventory_user_profile(request, pk=None):
    """
    Renders Inventory Staff profile page (inventory_base.html).
    """
    from inventory.models import InventoryAdjustment, InventoryUser, Rental

    if pk:
        profile_user = get_object_or_404(InventoryUser, pk=pk)
        if not can_manage_target_user(request.user, profile_user) and profile_user != request.user:
            messages.error(request, "Access Denied: You do not have permission to view this staff profile.")
            return redirect(get_default_redirect_for_role(request.user))
    else:
        inv_user_id = request.session.get("inv_user_id")
        if inv_user_id:
            profile_user = InventoryUser.objects.filter(id=inv_user_id).first() or request.user
        else:
            profile_user = request.user

    stats = {
        "adjustments_count": InventoryAdjustment.objects.filter(created_by=profile_user).count() if hasattr(profile_user, "created_by") or isinstance(profile_user, InventoryUser) else 0,
        "rentals_count": Rental.objects.filter(created_by=profile_user).count() if hasattr(profile_user, "created_by") or isinstance(profile_user, InventoryUser) else 0,
    }

    return render(
        request,
        "inventory/user_detail.html",
        {
            "profile_user": profile_user,
            "stats": stats,
        },
    )


@login_required
def user_create(request):
    """
    Creates a new Project Management User.
    PM_ADMIN can only create PM_MEMBER.
    ROOT can create PM_ADMIN or PM_MEMBER.
    """
    if not has_permission(request.user, PERMISSION_PROJECT_USER_MANAGE):
        messages.error(
            request, "Access Denied: You do not have permission to create PM users."
        )
        return redirect(get_default_redirect_for_role(request.user))

    form = UserCreateForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.save(commit=False)
            canonical_creator = get_canonical_role(request.user)

            # Enforce role assignment rules
            requested_role = form.cleaned_data.get("role") or ROLE_PM_MEMBER
            if canonical_creator == ROLE_PM_ADMIN:
                user.role = ROLE_PM_MEMBER
            else:
                if not can_assign_role(request.user, requested_role):
                    messages.error(
                        request, f"You are not allowed to assign role '{requested_role}'."
                    )
                    return render(
                        request,
                        "accounts/user_form.html",
                        {"form": form, "title": "Create New User", "action": "Create User"},
                    )
                user.role = requested_role

            user.save()
            messages.success(request, f'✅ User "{user.username}" created.')
            return redirect("accounts:user_detail", pk=user.pk)

        messages.error(request, "Please fix the errors below.")

    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Create New User", "action": "Create User"},
    )


@login_required
def user_detail(request, pk):
    """
    Renders user profile dashboard.
    """
    from tasks.models import Project, Task

    profile_user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, profile_user) and profile_user != request.user:
        messages.error(
            request, "Access Denied: You do not have permission to view this user profile."
        )
        return redirect(get_default_redirect_for_role(request.user))

    assigned_tasks = Task.objects.filter(assignees=profile_user).select_related(
        "project"
    )

    task_stats = {
        "total": assigned_tasks.count(),
        "todo": assigned_tasks.filter(status="todo").count(),
        "in_progress": assigned_tasks.filter(status="in_progress").count(),
        "done": assigned_tasks.filter(status="done").count(),
        "overdue": sum(1 for t in assigned_tasks if t.is_overdue),
    }

    return render(
        request,
        "accounts/user_detail.html",
        {
            "profile_user": profile_user,
            "assigned_tasks": assigned_tasks[:10],
            "managed_projects": Project.objects.filter(managers=profile_user),
            "member_projects": Project.objects.filter(members=profile_user),
            "task_stats": task_stats,
        },
    )


@login_required
def user_edit(request, pk):
    """
    Edits a PM user account.
    """
    edit_user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, edit_user):
        messages.error(
            request, "Access Denied: You cannot modify credentials for this user."
        )
        return redirect("accounts:user_list")

    form = UserEditForm(request.POST or None, instance=edit_user)

    if request.method == "POST":
        if form.is_valid():
            user = form.save(commit=False)
            canonical_admin = get_canonical_role(request.user)

            # Prevent self promotion or cross promotion
            if canonical_admin == ROLE_PM_ADMIN:
                user.role = ROLE_PM_MEMBER

            user.save()
            messages.success(
                request, f'User "{edit_user.username}" updated successfully.'
            )
            return redirect("accounts:user_detail", pk=edit_user.pk)

        messages.error(request, "Please fix the errors below.")

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "title": f"Edit User — {edit_user.username}",
            "action": "Save Changes",
            "edit_user": edit_user,
        },
    )


@login_required
def user_reset_password(request, pk):
    """
    Manual password override for a user account.
    """
    reset_user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, reset_user):
        messages.error(
            request, "Access Denied: You cannot reset password for this user."
        )
        return redirect("accounts:user_list")

    form = AdminPasswordResetForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            reset_user.set_password(form.cleaned_data["new_password1"])
            reset_user.save()
            messages.success(
                request, f'✅ Password for "{reset_user.username}" has been reset.'
            )
            return redirect("accounts:user_detail", pk=reset_user.pk)

        messages.error(request, "Please fix the errors below.")

    return render(
        request,
        "accounts/user_reset_password.html",
        {"form": form, "reset_user": reset_user},
    )


@login_required
def user_delete(request, pk):
    """
    Deactivates a user account.
    """
    del_user = get_object_or_404(User, pk=pk)

    if del_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("accounts:user_list")

    if not can_manage_target_user(request.user, del_user):
        messages.error(
            request, "Access Denied: You cannot delete/deactivate this user."
        )
        return redirect("accounts:user_list")

    if request.method == "POST":
        username = del_user.username
        del_user.is_active = False
        del_user.save(update_fields=["is_active"])
        messages.success(request, f'User "{username}" deactivated instead of deleted.')
        return redirect("accounts:user_list")

    return render(request, "accounts/user_confirm_delete.html", {"user_obj": del_user})


@login_required
def user_toggle_active(request, pk):
    """
    Toggles user active state.
    """
    toggle_user = get_object_or_404(User, pk=pk)

    if toggle_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_list")

    if not can_manage_target_user(request.user, toggle_user):
        messages.error(
            request, "Access Denied: You cannot toggle active status for this user."
        )
        return redirect("accounts:user_list")

    toggle_user.is_active = not toggle_user.is_active
    toggle_user.save()

    messages.success(
        request,
        f'User "{toggle_user.username}" {"activated" if toggle_user.is_active else "deactivated"}.',
    )
    return redirect(request.META.get("HTTP_REFERER", "accounts:user_list"))


@login_required
@require_POST
def change_user_role(request, pk):
    """
    AJAX endpoint to update user role.
    """
    target_user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, target_user):
        return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)

    if target_user == request.user:
        return JsonResponse(
            {"ok": False, "error": "You cannot change your own role here."}, status=400
        )

    new_role = request.POST.get("role", "")

    if not can_assign_role(request.user, new_role):
        return JsonResponse(
            {"ok": False, "error": f"You cannot assign role: {new_role}"}, status=403
        )

    old_role = target_user.get_role_display()
    target_user.role = new_role
    target_user.save()

    return JsonResponse(
        {
            "ok": True,
            "message": f"✅ {target_user.display_name} role changed from {old_role} to {target_user.get_role_display()}.",
            "new_role": new_role,
            "new_role_display": target_user.get_role_display(),
        }
    )


# ─── SECTION 3: INVENTORY USERS CRUD ───

@login_required
def inventory_user_create(request):
    """
    Creates an InventoryUser account.
    IM_ADMIN can create IM_MEMBER (staff) only.
    ROOT can create IM_ADMIN or IM_MEMBER.
    """
    from inventory.models import Branch, InventoryUser

    if not has_permission(request.user, PERMISSION_INVENTORY_USER_MANAGE):
        messages.error(
            request, "Access Denied: You do not have permission to manage Inventory Users."
        )
        return redirect("/accounts/users/?tab=inventory")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        requested_role = request.POST.get("role", "staff").strip()
        branch_id = request.POST.get("branch", "").strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/accounts/users/?tab=inventory")

        if InventoryUser.objects.filter(username=username).exists() or User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("/accounts/users/?tab=inventory")

        branch = Branch.objects.get(id=branch_id) if branch_id else None

        admin_role = get_canonical_role(request.user)
        if admin_role == ROLE_IM_ADMIN:
            final_role = "staff"  # IM_MEMBER
        else:
            final_role = requested_role if requested_role in ["super_admin", "branch_admin", "staff", "IM_ADMIN", "IM_MEMBER"] else "staff"

        user = InventoryUser.objects.create(
            username=username,
            email=email or None,
            role=final_role,
            branch=branch,
            is_active=True,
        )
        user.set_password(password)
        messages.success(request, f'Inventory user "{username}" created successfully.')

    return redirect("/accounts/users/?tab=inventory")


@login_required
def inventory_user_edit(request, pk):
    """
    Modifies InventoryUser account credentials & permissions.
    """
    from inventory.models import Branch, InventoryUser

    user = get_object_or_404(InventoryUser, pk=pk)

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot modify credentials for this inventory user."
        )
        return redirect("/accounts/users/?tab=inventory")

    if request.method == "POST":
        user.email = request.POST.get("email", "").strip() or None

        admin_role = get_canonical_role(request.user)
        if admin_role != ROLE_IM_ADMIN:
            user.role = request.POST.get("role", user.role).strip()

        branch_id = request.POST.get("branch", "").strip()
        user.branch = Branch.objects.get(id=branch_id) if branch_id else None
        user.is_active = request.POST.get("is_active") == "on"

        permission_fields = [
            "can_access_adjustments_page",
            "can_manage_adjustments",
            "can_access_serials_page",
            "can_manage_serials",
            "can_access_limits_page",
            "can_manage_limits",
            "can_access_alerts_page",
            "can_manage_alerts",
            "can_access_rentals_page",
            "can_manage_rentals",
            "can_access_shortage_page",
            "can_manage_shortage_exports",
            "can_view_all_branches_inventory",
            "can_add_inventory",
            "can_edit_inventory",
            "can_delete_inventory",
            "can_approve_transfer",
            "can_export_reports",
            "can_manage_users",
        ]
        for field in permission_fields:
            setattr(user, field, request.POST.get(field) == "on")

        password = request.POST.get("password", "").strip()
        if password:
            user.set_password(password)

        user.save()
        messages.success(request, f'Inventory user "{user.username}" updated successfully.')

    return redirect("/accounts/users/?tab=inventory")


@login_required
def inventory_user_delete(request, pk):
    """
    Deactivates an InventoryUser account.
    """
    from inventory.models import InventoryUser

    user = get_object_or_404(InventoryUser, pk=pk)

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot delete/deactivate this inventory user."
        )
        return redirect("/accounts/users/?tab=inventory")

    username = user.username
    user.is_active = False
    user.save(update_fields=["is_active"])
    messages.success(request, f'Inventory user "{username}" deactivated instead of deleted.')
    return redirect("/accounts/users/?tab=inventory")


@login_required
def inventory_user_toggle(request, pk):
    """
    Toggles is_active status of an InventoryUser.
    """
    from inventory.models import InventoryUser

    user = get_object_or_404(InventoryUser, pk=pk)

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot modify status for this inventory user."
        )
        return redirect("/accounts/users/?tab=inventory")

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f'Status of inventory user "{user.username}" updated.')
    return redirect("/accounts/users/?tab=inventory")


# ─── SECTION 4: TELESCOPE USERS CRUD ───

@login_required
def telescope_user_create(request):
    """
    Creates a Telescope Operator user in the dedicated TelescopeUser database table.
    """
    from telescope.models import TelescopeUser
    from inventory.models import InventoryUser

    if not has_permission(request.user, PERMISSION_TELESCOPE_USER_MANAGE):
        messages.error(
            request, "Access Denied: You do not have permission to manage Telescope Users."
        )
        return redirect("telescope:user_list")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("telescope:user_list")

        if User.objects.filter(username=username).exists() or InventoryUser.objects.filter(username=username).exists() or TelescopeUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists across system modules.")
            return redirect("telescope:user_list")

        admin_role = get_canonical_role(request.user)
        is_tele_admin = request.POST.get("is_telescope_admin") == "on"

        user = TelescopeUser.objects.create(
            username=username,
            email=email or None,
            role="admin" if is_tele_admin else "operator",
            is_active=request.POST.get("is_active") == "on",
            is_telescope_admin=is_tele_admin,
            can_operate_vbt=request.POST.get("can_operate_vbt") == "on",
            can_operate_jcbt=request.POST.get("can_operate_jcbt") == "on",
            can_operate_zeiss=request.POST.get("can_operate_zeiss") == "on",
            can_operate_cassegrain=request.POST.get("can_operate_cassegrain") == "on",
            can_operate_schmidt=request.POST.get("can_operate_schmidt") == "on",
            can_command_dome=request.POST.get("can_command_dome") == "on",
            can_trigger_exposures=request.POST.get("can_trigger_exposures") == "on",
        )
        user.set_password(password)
        messages.success(request, f'Telescope operator "{username}" created successfully.')

    return redirect("telescope:user_list")


@login_required
def telescope_user_edit(request, pk):
    """
    Edits a Telescope User's credentials and permissions.
    """
    from telescope.models import TelescopeUser

    try:
        user = TelescopeUser.objects.get(pk=pk)
        is_custom_model = True
    except TelescopeUser.DoesNotExist:
        user = get_object_or_404(User, pk=pk)
        is_custom_model = False

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot modify credentials for this telescope user."
        )
        return redirect("telescope:user_list")

    if request.method == "POST":
        user.email = request.POST.get("email", "").strip() or None
        user.is_active = request.POST.get("is_active") == "on"

        admin_role = get_canonical_role(request.user)
        if admin_role == ROLE_ROOT or getattr(request.user, "is_superuser", False):
            user.is_telescope_admin = request.POST.get("is_telescope_admin") == "on"

        permission_fields = [
            "can_operate_vbt",
            "can_operate_jcbt",
            "can_operate_zeiss",
            "can_operate_cassegrain",
            "can_operate_schmidt",
            "can_command_dome",
            "can_trigger_exposures",
        ]
        for field in permission_fields:
            setattr(user, field, request.POST.get(field) == "on")

        password = request.POST.get("password", "").strip()
        if password:
            user.set_password(password)
        else:
            user.save()

        messages.success(request, f'Telescope user "{user.username}" updated successfully.')

    return redirect("telescope:user_list")


@login_required
def telescope_user_delete(request, pk):
    """
    Deactivates a Telescope Operator.
    """
    from telescope.models import TelescopeUser

    try:
        user = TelescopeUser.objects.get(pk=pk)
    except TelescopeUser.DoesNotExist:
        user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot delete/deactivate this telescope user."
        )
        return redirect("telescope:user_list")

    username = user.username
    user.is_active = False
    user.save()
    messages.success(request, f'Telescope user "{username}" deactivated successfully.')
    return redirect("telescope:user_list")


@login_required
def telescope_user_toggle(request, pk):
    """
    Toggles active state of a Telescope Operator.
    """
    from telescope.models import TelescopeUser

    try:
        user = TelescopeUser.objects.get(pk=pk)
    except TelescopeUser.DoesNotExist:
        user = get_object_or_404(User, pk=pk)

    if not can_manage_target_user(request.user, user):
        messages.error(
            request, "Access Denied: You cannot modify status for this telescope user."
        )
        return redirect("telescope:user_list")

    user.is_active = not user.is_active
    user.save()
    messages.success(request, f'Status of telescope user "{user.username}" updated.')
    return redirect("telescope:user_list")
