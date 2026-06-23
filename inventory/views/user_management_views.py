from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from ..decorators import super_admin_required
from ..models import Branch, InventoryUser

"""
This module processes Inventory User catalog list rendering and staff creations/updates.
"""


@method_decorator(super_admin_required, name="dispatch")
class InventoryUserManagementView(View):
    """
    View class displaying, filtering and managing the isolated inventory staff list.
    Handles assigning granular view-based permissions to users.
    """
    PERMISSION_FIELDS = [
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

    def get(self, request):
        search = request.GET.get("q", "").strip()
        role_filter = request.GET.get("role", "").strip()
        status_filter = request.GET.get("status", "").strip()

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

        paginator = Paginator(users, 20)
        page_obj = paginator.get_page(request.GET.get("page"))
        branches = Branch.objects.all()

        return render(
            request,
            "inventory/users_management.html",
            {
                "users": page_obj.object_list,
                "page_obj": page_obj,
                "search": search,
                "role_filter": role_filter,
                "status_filter": status_filter,
                "branches": branches,
            },
        )

    def post(self, request):
        action = request.POST.get("action")
        if action == "create":
            username, password, email, role = (
                request.POST.get("username", "").strip(),
                request.POST.get("password", "").strip(),
                request.POST.get("email", "").strip(),
                request.POST.get("role", "staff").strip(),
            )
            if not username or not password:
                messages.error(request, "Username and password are required.")
                return redirect("inventory-users-management")
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if InventoryUser.objects.filter(username=username).exists() or User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists.")
                return redirect("inventory-users-management")

            branch_id = request.POST.get("branch")
            branch = Branch.objects.get(id=branch_id) if branch_id else None
            user = InventoryUser.objects.create(
                username=username,
                email=email or None,
                role=role,
                branch=branch,
                is_active=True,
            )
            user.set_password(password)
            messages.success(request, f'Inventory user "{username}" created.')
            return redirect("inventory-users-management")

        user_id = request.POST.get("user_id")
        target_user = get_object_or_404(InventoryUser, id=user_id)

        if action == "update":
            target_user.email = request.POST.get("email", "").strip() or None
            target_user.role = request.POST.get("role", target_user.role).strip()
            branch_id = request.POST.get("branch")
            target_user.branch = Branch.objects.get(id=branch_id) if branch_id else None
            target_user.is_active = request.POST.get("is_active") == "on"
            update_fields = ["email", "role", "branch", "is_active"]
            for field_name in self.PERMISSION_FIELDS:
                setattr(target_user, field_name, request.POST.get(field_name) == "on")
                update_fields.append(field_name)
            target_user.save(update_fields=update_fields)
            new_password = request.POST.get("password", "").strip()
            if new_password:
                target_user.set_password(new_password)
            messages.success(request, f'Updated "{target_user.username}".')
            return redirect("inventory-users-management")

        if action == "toggle_active":
            if target_user.id == request.user.id:
                messages.error(request, "You cannot deactivate your own account.")
                return redirect("inventory-users-management")
            target_user.is_active = not target_user.is_active
            target_user.save(update_fields=["is_active"])
            messages.success(request, f'"{target_user.username}" status updated.')
            return redirect("inventory-users-management")

        if action == "delete":
            if target_user.id == request.user.id:
                messages.error(request, "You cannot delete your own account.")
                return redirect("inventory-users-management")
            username = target_user.username
            target_user.delete()
            messages.success(request, f'Inventory user "{username}" deleted.')
            return redirect("inventory-users-management")

        messages.error(request, "Invalid action.")
        return redirect("inventory-users-management")
