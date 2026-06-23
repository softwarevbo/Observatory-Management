from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from ..decorators import branch_admin_required
from ..models import BranchStock, InventoryUser, InventoryAdjustment
from stock.models import StockEntry

"""
This module processes branch administration dashboards and user permission views.
"""


@method_decorator(branch_admin_required, name="dispatch")
class BranchAdminDashboardView(View):
    """
    View class rendering metrics, staff counts, recent adjustments, 
    and entries specific to the currently logged-in Branch Admin's branch.
    """
    def get(self, request):
        branch = request.user.branch
        if not branch:
            messages.error(request, "You are not assigned to any branch.")
            return redirect("dashboard-page")

        total_staff = InventoryUser.objects.filter(branch=branch, role="staff").count()
        branch_stock_qs = BranchStock.objects.filter(branch=branch)
        total_products_in_branch = branch_stock_qs.count()
        total_quantity = (
            branch_stock_qs.aggregate(total=Sum("current_quantity"))["total"] or 0
        )
        recent_stock = StockEntry.objects.filter(branch=branch).order_by("-timestamp")[
            :5
        ]
        recent_adjustments = InventoryAdjustment.objects.filter(branch=branch).order_by(
            "-timestamp"
        )[:5]

        context = {
            "branch": branch,
            "total_staff": total_staff,
            "total_products": total_products_in_branch,
            "total_quantity": total_quantity,
            "recent_stock": recent_stock,
            "recent_adjustments": recent_adjustments,
        }
        return render(request, "inventory/branch_admin/dashboard.html", context)


@method_decorator(branch_admin_required, name="dispatch")
class BranchStaffManagementView(View):
    """
    View class displaying staff lists and processing updates to staff status
    and permission attributes inside the branch scope.
    """
    def get(self, request):
        branch = request.user.branch
        staff = InventoryUser.objects.filter(branch=branch, role="staff")
        return render(
            request,
            "inventory/branch_admin/staff.html",
            {"staff": staff, "branch": branch},
        )

    def post(self, request):
        branch = request.user.branch
        action = request.POST.get("action")
        if action == "create":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "").strip()
            if not username or not password:
                messages.error(request, "Username and password are required.")
            else:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                if InventoryUser.objects.filter(username=username).exists() or User.objects.filter(username=username).exists():
                    messages.error(request, "Username already exists.")
                else:
                    user = InventoryUser.objects.create(
                        username=username, branch=branch, role="staff"
                    )
                    user.set_password(password)
                    messages.success(request, f"Staff user '{username}' created.")
        elif action == "toggle_status":
            user_id = request.POST.get("user_id")
            try:
                user = InventoryUser.objects.get(id=user_id, branch=branch)
                user.is_active = not user.is_active
                user.save()
                messages.success(request, f"User status updated.")
            except InventoryUser.DoesNotExist:
                messages.error(request, "User not found.")
        elif action == "update_permissions":
            user_id = request.POST.get("user_id")
            try:
                user = InventoryUser.objects.get(id=user_id, branch=branch)
                user.can_add_inventory = request.POST.get("can_add") == "on"
                user.can_edit_inventory = request.POST.get("can_edit") == "on"
                user.can_delete_inventory = request.POST.get("can_delete") == "on"
                user.save()
                messages.success(request, f"Permissions updated for {user.username}.")
            except InventoryUser.DoesNotExist:
                messages.error(request, "User not found.")
        return redirect("branch-users")
