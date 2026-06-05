from django.contrib import messages
from django.db.models import Sum, Count
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from audit.models import AuditLog
from products.models import Product
from stock.models import StockEntry
from ..decorators import super_admin_required
from ..models import Branch, InventoryUser, InventoryAdjustment

"""
This module processes global multi-branch analytics dashboards and branch creation/deletions.
"""


@method_decorator(super_admin_required, name="dispatch")
class SuperAdminDashboardView(View):
    """
    Dashboard view aggregating storage metrics across all branches.
    Provides counts, total calculated stock, branch summaries, and recent activity logs.
    """
    def get(self, request):
        total_branches = Branch.objects.count()
        total_users = InventoryUser.objects.count()
        total_products = Product.objects.count()

        total_stock_in = (
            StockEntry.objects.filter(entry_type="in").aggregate(total=Sum("quantity"))[
                "total"
            ]
            or 0
        )
        total_stock_out = (
            StockEntry.objects.filter(entry_type="out").aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        )
        total_adjustments = (
            InventoryAdjustment.objects.aggregate(total=Sum("quantity"))["total"] or 0
        )
        current_total_stock = total_stock_in + total_adjustments - total_stock_out

        branches = Branch.objects.annotate(
            user_count=Count("users", distinct=True),
            product_count=Count("stocks", distinct=True),
        )
        recent_activities = AuditLog.objects.order_by("-timestamp")[:10]

        context = {
            "total_branches": total_branches,
            "total_users": total_users,
            "total_products": total_products,
            "current_total_stock": current_total_stock,
            "branches": branches,
            "recent_activities": recent_activities,
        }
        return render(request, "inventory/superadmin/dashboard.html", context)


@method_decorator(super_admin_required, name="dispatch")
class BranchManagementView(View):
    """
    View class displaying branch listings and managing creating, updating, and deleting branch objects.
    """
    def get(self, request):
        branches = Branch.objects.annotate(user_count=Count("users"))
        return render(
            request, "inventory/superadmin/branches.html", {"branches": branches}
        )

    def post(self, request):
        action = request.POST.get("action")
        if action == "create":
            code = request.POST.get("code", "").strip().lower()
            name = request.POST.get("name", "").strip()
            if not code or not name:
                messages.error(request, "Code and Name are required.")
            elif Branch.objects.filter(code=code).exists():
                messages.error(request, "A branch with this code already exists.")
            else:
                Branch.objects.create(code=code, name=name)
                messages.success(request, f"Branch '{name}' created successfully.")
        elif action == "update":
            branch_id = request.POST.get("branch_id")
            name = request.POST.get("name", "").strip()
            try:
                branch = Branch.objects.get(id=branch_id)
                branch.name = name
                branch.save()
                messages.success(request, f"Branch '{name}' updated successfully.")
            except Branch.DoesNotExist:
                messages.error(request, "Branch not found.")
        elif action == "delete":
            branch_id = request.POST.get("branch_id")
            try:
                branch = Branch.objects.get(id=branch_id)
                if branch.users.exists() or branch.stocks.exists():
                    messages.error(
                        request, "Cannot delete branch with active users or stock."
                    )
                else:
                    name = branch.name
                    branch.delete()
                    messages.success(request, f"Branch '{name}' deleted successfully.")
            except Branch.DoesNotExist:
                messages.error(request, "Branch not found.")
        return redirect("inventory-branches")
