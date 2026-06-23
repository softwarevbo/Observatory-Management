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

"""
This module handles User Administration and Management Views.
It is secured by `@login_required` and `@admin_required` decorators, meaning
only authenticated administrators can perform operations within these endpoints.

Key capabilities:
1. Unified User List view partitioned into tabs for Project Management, Inventory, and Telescope.
2. Filter & Search capabilities on user lists using Q objects.
3. Pagination of users using Django's Paginator class.
4. CRUD operations for standard Project Management users, separate Inventory users, and Telescope operators.
5. Password resets and role changes.
"""

@login_required
@admin_required
def user_list(request):
    """
    Lists users based on selected system category tabs (Project Management 'pm', 'inventory', or 'telescope').
    Supports searching by text and filtering by role, department/team, and account status.
    """
    from inventory.models import Branch, InventoryUser

    # Identify the active portal tab (defaults to PM user list)
    active_tab = request.GET.get("tab", "pm")
    
    # Retrieve query and filter options from the request's GET parameters
    search, role_filter, team_filter, status_filter = (
        request.GET.get("q", ""),
        request.GET.get("role", ""),
        request.GET.get("team", ""),
        request.GET.get("status", ""),
    )

    # ─── SECTION 1: INVENTORY USERS LISTING ───
    if active_tab == "inventory":
        users = InventoryUser.objects.all().order_by("-created_at")
        
        # Apply filters if present
        if search:
            # Match search input against username or email (case-insensitive)
            users = users.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            )
        if role_filter:
            users = users.filter(role=role_filter)
        if status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "inactive":
            users = users.filter(is_active=False)

        # Compute summary metrics to render in the header cards
        stats = {
            "total": InventoryUser.objects.count(),
            "active": InventoryUser.objects.filter(is_active=True).count(),
            "inactive": InventoryUser.objects.filter(is_active=False).count(),
            "super_admins": InventoryUser.objects.filter(role="super_admin").count(),
            "branch_admins": InventoryUser.objects.filter(role="branch_admin").count(),
            "staff": InventoryUser.objects.filter(role="staff").count(),
        }
        
        # Paginate results showing 10 inventory users per page
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

    # ─── SECTION 2: TELESCOPE & PROJECT MANAGEMENT USERS LISTING ───
    # Standard User model stores both PM users and Telescope operators
    if active_tab == "telescope":
        # Operators have the 'can_access_telescope' flag enabled
        users = User.objects.filter(can_access_telescope=True).order_by("-date_joined")
    else:
        # PM users have the 'can_access_pm' flag enabled
        users = User.objects.filter(can_access_pm=True).order_by("-date_joined")

    # Apply filters
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

    # Compute status statistics depending on which list is viewed
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

    # Paginate results (10 users per page)
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
    """
    Renders and processes user registration form to create a new Project Management User.
    """
    form = UserCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            # Save the new user instance
            user = form.save()
            messages.success(request, f'✅ User "{user.username}" created.')
            # Redirect to the detail page of the newly created user profile
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
    """
    Renders the profile dashboard of a specific user.
    Shows assigned tasks and metrics for that specific user.
    """
    from tasks.models import Project, Task

    # Fetch the user using primary key (pk) or raise 404 error if not found
    profile_user = get_object_or_404(User, pk=pk)
    
    # Query tasks assigned to this user.
    # select_related performs a SQL join to fetch related project data in a single query (performance optimization).
    assigned_tasks = Task.objects.filter(assignees=profile_user).select_related(
        "project"
    )
    
    # Calculate task metrics for this specific user
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
            "assigned_tasks": assigned_tasks[:10], # Limit list to top 10 tasks
            "managed_projects": Project.objects.filter(managers=profile_user),
            "member_projects": Project.objects.filter(members=profile_user),
            "task_stats": task_stats,
        },
    )


@login_required
@admin_required
def user_edit(request, pk):
    """
    Edits a PM user's account details.
    """
    edit_user = get_object_or_404(User, pk=pk)
    # Bind form to the edit_user instance for pre-populating inputs
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
    """
    Allows admins to perform manual password overrides for a user account.
    """
    reset_user = get_object_or_404(User, pk=pk)
    form = AdminPasswordResetForm(request.POST or None)
    
    if request.method == "POST":
        if form.is_valid():
            # Update password and save changes
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
    """
    Permanently deletes a user account. Includes safety guard against self-deletion.
    """
    del_user = get_object_or_404(User, pk=pk)
    
    # Safety guard: prevent self-deletion
    if del_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("accounts:user_list")
        
    if request.method == "POST":
        username = del_user.username
        # Deactivate user instead of delete
        del_user.is_active = False
        del_user.save(update_fields=["is_active"])
        messages.success(request, f'User "{username}" deactivated instead of deleted.')
        return redirect("accounts:user_list")
        
    return render(request, "accounts/user_confirm_delete.html", {"user_obj": del_user})


@login_required
@admin_required
def user_toggle_active(request, pk):
    """
    Deactivates or activates a user.
    Deactivating blocks authentication while preserving historical task/project links.
    """
    toggle_user = get_object_or_404(User, pk=pk)
    
    # Safety guard: prevent self-deactivation
    if toggle_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_list")
        
    # Toggle boolean state
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
    AJAX endpoint to quickly update a user's role on the list view.
    Only allows requests originating from POST protocol. Returns JsonResponse.
    """
    # Authorization checks
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
    
    # Check if role value is defined inROLE_CHOICES
    if new_role not in [r[0] for r in User.ROLE_CHOICES]:
        return JsonResponse(
            {"ok": False, "error": f"Invalid role: {new_role}"}, status=400
        )
        
    old_role = target_user.get_role_display()
    target_user.role = new_role
    
    # Optimizes DB save by updating only the 'role' field column
    target_user.save(update_fields=["role"])
    
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
@admin_required
def inventory_user_create(request):
    """
    Creates an InventoryUser account utilizing manual POST parsing.
    """
    from inventory.models import Branch, InventoryUser
    
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        role = request.POST.get("role", "staff").strip()
        branch_id = request.POST.get("branch", "").strip()

        # Validate mandatory input fields
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/accounts/users/?tab=inventory")

        # Validate username uniqueness
        if InventoryUser.objects.filter(username=username).exists() or User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("/accounts/users/?tab=inventory")

        # Resolve inventory warehouse branch linkage
        branch = Branch.objects.get(id=branch_id) if branch_id else None
        
        # Create inventory user instance
        user = InventoryUser.objects.create(
            username=username,
            email=email or None,
            role=role,
            branch=branch,
            is_active=True,
        )
        # Hash user password
        user.set_password(password)
        messages.success(request, f'Inventory user "{username}" created successfully.')
        
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def inventory_user_edit(request, pk):
    """
    Modifies an InventoryUser account credentials and granular permission toggles.
    """
    from inventory.models import Branch, InventoryUser
    
    user = get_object_or_404(InventoryUser, pk=pk)
    
    if request.method == "POST":
        # Update details
        user.email = request.POST.get("email", "").strip() or None
        user.role = request.POST.get("role", user.role).strip()
        
        branch_id = request.POST.get("branch", "").strip()
        user.branch = Branch.objects.get(id=branch_id) if branch_id else None
        user.is_active = request.POST.get("is_active") == "on"

        # Apply checkbox values for inventory permissions
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
        # Iterate over attributes and check POST dictionary
        for field in permission_fields:
            setattr(user, field, request.POST.get(field) == "on")

        # Handle password override if supplied
        password = request.POST.get("password", "").strip()
        if password:
            user.set_password(password)

        user.save()
        messages.success(request, f'Inventory user "{user.username}" updated successfully.')
        
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def inventory_user_delete(request, pk):
    """
    Deactivates an InventoryUser account instead of deleting.
    """
    from inventory.models import InventoryUser
    
    user = get_object_or_404(InventoryUser, pk=pk)
    username = user.username
    user.is_active = False
    user.save(update_fields=["is_active"])
    messages.success(request, f'Inventory user "{username}" deactivated instead of deleted.')
    return redirect("/accounts/users/?tab=inventory")


@login_required
@admin_required
def inventory_user_toggle(request, pk):
    """
    Toggles the is_active status of an InventoryUser.
    """
    from inventory.models import InventoryUser
    
    user = get_object_or_404(InventoryUser, pk=pk)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f'Status of inventory user "{user.username}" updated.')
    return redirect("/accounts/users/?tab=inventory")


# ─── SECTION 4: TELESCOPE USERS CRUD ───

@login_required
@admin_required
def telescope_user_create(request):
    """
    Creates a new Telescope Operator user with default telescope access.
    Telescope users are standard Users but with configured telescope specific flags.
    """
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/accounts/users/?tab=telescope")

        from inventory.models import InventoryUser
        if User.objects.filter(username=username).exists() or InventoryUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("/accounts/users/?tab=telescope")

        # Create user instance using helper method `create_user` (handles hashing automatically)
        user = User.objects.create_user(
            username=username,
            email=email or None,
            password=password,
            can_access_pm=False,
            can_access_inventory=False,
            can_access_telescope=True, # Grant access to telescope dashboard portal
            is_active=True,
        )
        user.is_active = request.POST.get("is_active") == "on"
        user.is_telescope_admin = request.POST.get("is_telescope_admin") == "on"

        # Apply specific instrument operation checkboxes
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
    """
    Edits a Telescope User's credentials and granular operator permissions.
    """
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
    """
    Deactivates a Telescope Operator instead of deleting.
    """
    user = get_object_or_404(User, pk=pk)
    username = user.username
    user.is_active = False
    user.save(update_fields=["is_active"])
    messages.success(request, f'Telescope user "{username}" deactivated instead of deleted.')
    return redirect("/accounts/users/?tab=telescope")


@login_required
@admin_required
def telescope_user_toggle(request, pk):
    """
    Toggles the active state of a Telescope Operator.
    """
    user = get_object_or_404(User, pk=pk)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f'Status of telescope user "{user.username}" updated.')
    return redirect("/accounts/users/?tab=telescope")
