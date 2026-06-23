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
            target_user.is_active = False
            target_user.save(update_fields=["is_active"])
            messages.success(request, f'Inventory user "{username}" deactivated instead of deleted.')
            return redirect("inventory-users-management")

        messages.error(request, "Invalid action.")
        return redirect("inventory-users-management")


class InventoryUserPermissionsView(View):
    """
    Dedicated view for managing granular inventory permissions for staff users.
    Enforces role-based authority rules for both Branch Admins and Super Admins.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not getattr(request.user, "is_admin", False):
            messages.error(request, "You do not have permission to access the permissions page.")
            return redirect("dashboard-page")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, user_id):
        target_user = get_object_or_404(InventoryUser, id=user_id)
        
        # Enforce restrictions
        # 1. Branch Admin restrictions
        if getattr(request.user, "is_branch_admin", False) and not getattr(request.user, "is_super_admin", False):
            if target_user.role != "staff" or target_user.branch != request.user.branch:
                messages.error(request, "Access Denied: You can only edit permissions for staff in your own branch.")
                return redirect("branch-users")
        
        # 2. Prevent editing self
        if request.user.id == target_user.id:
            messages.error(request, "Access Denied: You cannot modify your own permissions.")
            if getattr(request.user, "is_super_admin", False):
                return redirect("inventory-users-management")
            else:
                return redirect("branch-users")

        permission_groups = {
            "page_access": [
                {"name": "can_access_adjustments_page", "label": "Access Stock Adjustments Page", "desc": "Allows viewing the stock adjustments logs page."},
                {"name": "can_access_serials_page", "label": "Access Serial Numbers Tracking Page", "desc": "Allows viewing the list of registered serial/lot numbers."},
                {"name": "can_access_limits_page", "label": "Access Stock Limits / Reorder Limits Page", "desc": "Allows viewing branch-specific inventory quantity thresholds."},
                {"name": "can_access_alerts_page", "label": "Access Active Alerts Page", "desc": "Allows viewing low stock and expiry alerts logs."},
                {"name": "can_access_rentals_page", "label": "Access Rentals Page", "desc": "Allows viewing active equipment rental transactions."},
                {"name": "can_access_shortage_page", "label": "Access Shortage / Out of Stock Page", "desc": "Allows viewing lists of items below minimum quantities."},
            ],
            "actions": [
                {"name": "can_manage_adjustments", "label": "Manage Stock Adjustments", "desc": "Allows creating new manual stock adjustments (increments/decrements)."},
                {"name": "can_manage_serials", "label": "Manage Serial Numbers", "desc": "Allows registering or editing serial numbers for equipment."},
                {"name": "can_manage_limits", "label": "Manage Stock Limits", "desc": "Allows setting, editing, or removing reorder thresholds."},
                {"name": "can_manage_alerts", "label": "Manage / Acknowledge Alerts", "desc": "Allows acknowledging or resolving triggered stock level alerts."},
                {"name": "can_manage_rentals", "label": "Manage Rentals Actions", "desc": "Allows creating rentals, registering returns, and managing overdue items."},
                {"name": "can_manage_shortage_exports", "label": "Export Shortage Data", "desc": "Allows exporting CSV/PDF files of out-of-stock items lists."},
            ],
            "core": [
                {"name": "can_add_inventory", "label": "Create Products / Add Stock Items", "desc": "Allows inserting new products into the branch inventory catalog."},
                {"name": "can_edit_inventory", "label": "Edit Products / Modify Stock Items", "desc": "Allows editing details and location values of existing products."},
                {"name": "can_delete_inventory", "label": "Delete Products / Archive Stock Items", "desc": "Allows permanently removing products from the inventory."},
                {"name": "can_approve_transfer", "label": "Approve Stock Transfers", "desc": "Allows approving and receiving stock transfers between branches."},
                {"name": "can_export_reports", "label": "Export Inventory Reports", "desc": "Allows downloading reports for stock analytics and statistics."},
            ],
            "admin_global": [
                {"name": "can_view_all_branches_inventory", "label": "Global Inventory Access (Cross-Branch)", "desc": "Allows viewing products and stock logs across all physical branches."},
                {"name": "can_manage_users", "label": "Administrate Inventory Users", "desc": "Allows creating, updating, or deleting other inventory staff accounts."},
            ]
        }

        # Build flat list of all checked state variables
        user_perms = {}
        for group_name, group_list in permission_groups.items():
            for p in group_list:
                user_perms[p["name"]] = getattr(target_user, p["name"], False)

        context = {
            "target_user": target_user,
            "permission_groups": permission_groups,
            "user_perms": user_perms,
        }
        return render(request, "inventory/user_permissions.html", context)

    def post(self, request, user_id):
        target_user = get_object_or_404(InventoryUser, id=user_id)
        
        # Enforce restrictions
        # 1. Branch Admin restrictions
        if getattr(request.user, "is_branch_admin", False) and not getattr(request.user, "is_super_admin", False):
            if target_user.role != "staff" or target_user.branch != request.user.branch:
                messages.error(request, "Access Denied: You can only edit permissions for staff in your own branch.")
                return redirect("branch-users")
        
        # 2. Prevent editing self
        if request.user.id == target_user.id:
            messages.error(request, "Access Denied: You cannot modify your own permissions.")
            if getattr(request.user, "is_super_admin", False):
                return redirect("inventory-users-management")
            else:
                return redirect("branch-users")

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

        update_fields = []
        for field in permission_fields:
            val = request.POST.get(field) == "on"
            setattr(target_user, field, val)
            update_fields.append(field)
            
        target_user.save(update_fields=update_fields)
        messages.success(request, f"Granular permissions updated for '{target_user.username}'.")
        
        if getattr(request.user, "is_super_admin", False):
            return redirect("inventory-users-management")
        else:
            return redirect("branch-users")
