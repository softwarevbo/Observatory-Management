from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from tasks.decorators import admin_required
from ..models import User
from ..forms import AdminPasswordResetForm, UserCreateForm, UserEditForm


@login_required
@admin_required
def user_list(request):
    from inventory.models import Branch, InventoryUser

    active_tab = request.GET.get("tab", "pm")
    search, role_filter, team_filter, status_filter = (
        request.GET.get("q", ""),
        request.GET.get("role", ""),
        request.GET.get("team", ""),
        request.GET.get("status", ""),
    )

    if active_tab == "inventory":
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
            "accounts/user_list.html",
            {
                "users": page_obj,
                "page_obj": page_obj,
                "stats": stats,
                "search": search,
                "role_filter": role_filter,
                "status_filter": status_filter,
                "active_tab": active_tab,
                "branches": Branch.objects.all(),
                "role_choices": [
                    ("super_admin", "Super Admin"),
                    ("branch_admin", "Branch Admin"),
                    ("staff", "Staff"),
                ],
            },
        )

    if active_tab == "telescope":
        users = User.objects.filter(can_access_telescope=True).order_by("-date_joined")
    else:
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

    if active_tab == "telescope":
        stats = {
            "total": User.objects.filter(can_access_telescope=True).count(),
            "active": User.objects.filter(can_access_telescope=True, is_active=True).count(),
            "inactive": User.objects.filter(can_access_telescope=True, is_active=False).count(),
            "vbt_operators": User.objects.filter(can_access_telescope=True, can_operate_vbt=True).count(),
            "jcbt_operators": User.objects.filter(can_access_telescope=True, can_operate_jcbt=True).count(),
        }
    else:
        stats = {
            "total": User.objects.filter(can_access_pm=True).count(),
            "active": User.objects.filter(can_access_pm=True, is_active=True).count(),
            "inactive": User.objects.filter(can_access_pm=True, is_active=False).count(),
            "admins": User.objects.filter(can_access_pm=True, role="admin").count(),
            "managers": User.objects.filter(can_access_pm=True, role="project_manager").count(),
            "members": User.objects.filter(can_access_pm=True, role="member").count(),
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
            "active_tab": active_tab,
        },
    )


@login_required
@admin_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            messages.success(request, f'✅ User "{user.username}" created.')
            return redirect("accounts:user_detail", pk=user.pk)
        messages.error(request, "Please fix the errors below.")
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Create New User", "action": "Create User"},
    )


@login_required
@admin_required
def user_detail(request, pk):
    from tasks.models import Project, Task

    profile_user = get_object_or_404(User, pk=pk)
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
@admin_required
def user_edit(request, pk):
    edit_user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=edit_user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
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
@admin_required
def user_reset_password(request, pk):
    reset_user = get_object_or_404(User, pk=pk)
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
@admin_required
def user_delete(request, pk):
    del_user = get_object_or_404(User, pk=pk)
    if del_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("accounts:user_list")
    if request.method == "POST":
        username = del_user.username
        del_user.delete()
        messages.success(request, f'User "{username}" permanently deleted.')
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"user_obj": del_user})


@login_required
@admin_required
def user_toggle_active(request, pk):
    toggle_user = get_object_or_404(User, pk=pk)
    if toggle_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
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
    if not (request.user.is_superuser or request.user.is_admin):
        return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)
    target_user = get_object_or_404(User, pk=pk)
    if target_user.is_superuser and not request.user.is_superuser:
        return JsonResponse(
            {"ok": False, "error": "Cannot change a superuser account."}, status=403
        )
    if target_user == request.user:
        return JsonResponse(
            {"ok": False, "error": "You cannot change your own role here."}, status=400
        )
    new_role = request.POST.get("role", "")
    if new_role not in [r[0] for r in User.ROLE_CHOICES]:
        return JsonResponse(
            {"ok": False, "error": f"Invalid role: {new_role}"}, status=400
        )
    old_role = target_user.get_role_display()
    target_user.role = new_role
    target_user.save(update_fields=["role"])
    return JsonResponse(
        {
            "ok": True,
            "message": f"✅ {target_user.display_name} role changed from {old_role} to {target_user.get_role_display()}.",
            "new_role": new_role,
            "new_role_display": target_user.get_role_display(),
        }
    )


@login_required
@admin_required
def inventory_user_create(request):
    from inventory.models import Branch, InventoryUser
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        role = request.POST.get("role", "staff").strip()
        branch_id = request.POST.get("branch", "").strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/accounts/users/?tab=inventory")

        if InventoryUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("/accounts/users/?tab=inventory")

        branch = Branch.objects.get(id=branch_id) if branch_id else None
        user = InventoryUser.objects.create(
            username=username,
            email=email or None,
            role=role,
            branch=branch,
            is_active=True,
        )
        user.set_password(password)
        messages.success(request, f'Inventory user "{username}" created successfully.')
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def inventory_user_edit(request, pk):
    from inventory.models import Branch, InventoryUser
    user = get_object_or_404(InventoryUser, pk=pk)
    if request.method == "POST":
        user.email = request.POST.get("email", "").strip() or None
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
@admin_required
def inventory_user_delete(request, pk):
    from inventory.models import InventoryUser
    user = get_object_or_404(InventoryUser, pk=pk)
    username = user.username
    user.delete()
    messages.success(request, f'Inventory user "{username}" deleted successfully.')
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def inventory_user_toggle(request, pk):
    from inventory.models import InventoryUser
    user = get_object_or_404(InventoryUser, pk=pk)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f'Status of inventory user "{user.username}" updated.')
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def telescope_user_create(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/accounts/users/?tab=telescope")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("/accounts/users/?tab=telescope")

        user = User.objects.create_user(
            username=username,
            email=email or None,
            password=password,
            can_access_pm=False,
            can_access_inventory=False,
            can_access_telescope=True,
            is_active=True,
        )
        user.is_active = request.POST.get("is_active") == "on"
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
        user.save()
        messages.success(request, f'Telescope user "{username}" created successfully.')
    return redirect("/accounts/users/?tab=telescope")


@login_required
@admin_required
def telescope_user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        user.email = request.POST.get("email", "").strip() or None
        user.is_active = request.POST.get("is_active") == "on"
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

        user.save()
        messages.success(request, f'Telescope user "{user.username}" updated successfully.')
    return redirect("/accounts/users/?tab=telescope")


@login_required
@admin_required
def telescope_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    username = user.username
    user.delete()
    messages.success(request, f'Telescope user "{username}" deleted successfully.')
    return redirect("/accounts/users/?tab=telescope")


@login_required
@admin_required
def telescope_user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f'Status of telescope user "{user.username}" updated.')
    return redirect("/accounts/users/?tab=telescope")
