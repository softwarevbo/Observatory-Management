from django.db import models
from django.shortcuts import redirect, render
from django.views import View

from inventory.models import InventoryAdjustment
from products.models import Product
from stock.models import StockEntry


class DashboardOverview(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Placeholder data for dashboard KPIs and stock levels
        data = {
            "total_products": 100,
            "total_stock": 5000,
            "alerts": [],
            "kpis": {
                "stock_turnover": 5.2,
                "shrinkage_rate": 0.02,
            },
        }
        return render(request, "dashboard/overview.html", data)


class DashboardPageView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if request.user.is_super_admin:
            return redirect("superadmin-dashboard")
        if request.user.is_branch_admin:
            return redirect("branch-dashboard")

        from inventory.utils import get_isolated_products, has_global_inventory_access
        from inventory.models import BranchStock, InventoryAdjustment, Alert

        is_global = has_global_inventory_access(request.user)
        user_branch = getattr(request.user, "branch", None)

        products_qs = get_isolated_products(request.user)
        total_products = products_qs.count()

        # 1. Total Current Stock (Branch Isolated)
        if is_global:
            current_total_stock = (
                BranchStock.objects.aggregate(total=models.Sum("current_quantity"))[
                    "total"
                ]
                or 0
            )
        elif user_branch:
            current_total_stock = (
                BranchStock.objects.filter(branch=user_branch).aggregate(
                    total=models.Sum("current_quantity")
                )["total"]
                or 0
            )
        else:
            current_total_stock = 0

        # 2. Turnover and Shrinkage (Branch Isolated)
        from inventory.utils import filter_by_branch

        # Total Stock In/Out for the branch
        stock_entries = filter_by_branch(StockEntry.objects.all(), request.user)
        total_stock_in = (
            stock_entries.filter(entry_type="in").aggregate(
                total=models.Sum("quantity")
            )["total"]
            or 0
        )
        total_stock_out = (
            stock_entries.filter(entry_type="out").aggregate(
                total=models.Sum("quantity")
            )["total"]
            or 0
        )

        # Adjustments for the branch
        adjustments = filter_by_branch(InventoryAdjustment.objects.all(), request.user)
        positive_adj = (
            adjustments.filter(adjustment_type="increase").aggregate(
                total=models.Sum("quantity")
            )["total"]
            or 0
        )
        negative_adj = (
            adjustments.filter(adjustment_type="decrease").aggregate(
                total=models.Sum("quantity")
            )["total"]
            or 0
        )

        # Calculation Metrics
        average_inventory = (
            ((total_stock_in + current_total_stock) / 2)
            if (total_stock_in + current_total_stock) > 0
            else 1
        )
        stock_turnover = (
            round(total_stock_out / average_inventory, 2) if average_inventory else 0
        )

        shrinkage_base = total_stock_in + positive_adj
        shrinkage_rate = (
            round((abs(negative_adj) / shrinkage_base) * 100, 2)
            if shrinkage_base
            else 0
        )

        # 3. Alerts (Branch Isolated)
        alerts_qs = filter_by_branch(
            Alert.objects.all(), request.user, "product__branch"
        )
        recent_alerts = alerts_qs.filter(status="active").order_by("-created_at")[:5]

        context = {
            "total_products": total_products,
            "total_stock": current_total_stock,
            "stock_turnover": stock_turnover,
            "shrinkage_rate": shrinkage_rate,
            "alerts": recent_alerts,
        }
        return render(request, "dashboard/overview.html", context)
