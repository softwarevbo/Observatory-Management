from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditLog
from products.models import Product
from tasks.decorators import admin_required
from ..models import InventoryAdjustment, Branch
from ..serializers import InventoryAdjustmentSerializer
from ..notifications import notify_inventory_admins
from ..utils import get_isolated_products, filter_by_branch, has_global_inventory_access

"""
This module processes stock adjustments tracking, permission routing overrides, and DRF API endpoints.
"""

def _inventory_permission_redirect(request, access_field=None, manage_field=None):
    """
    Utility checking user credentials on specific sub-modules.
    Super admin and branch admin bypass this validation.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if getattr(request.user, "is_super_admin", False) or getattr(request.user, "is_branch_admin", False):
        return None
    if access_field and not getattr(request.user, access_field, True):
        messages.error(request, "You do not have access to this inventory module.")
        return redirect("dashboard-page")
    if (
        request.method == "POST"
        and manage_field
        and not getattr(request.user, manage_field, True)
    ):
        messages.error(
            request, "You do not have permission to perform this management action."
        )
        return redirect("dashboard-page")
    return None


@method_decorator(admin_required, name="dispatch")
class InventoryAdjustmentPageView(View):
    """
    View class displaying stock adjustment logs, applying branch isolates.
    Enables creating manual adjustments with automatic logging hook triggers.
    """
    def get(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_adjustments_page"
        )
        if permission_redirect:
            return permission_redirect

        products = get_isolated_products(request.user)
        adjustments = filter_by_branch(
            InventoryAdjustment.objects.all(), request.user
        ).order_by("-timestamp")
        paginator = Paginator(adjustments, 50)
        page_number = request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        branches = (
            Branch.objects.all() if has_global_inventory_access(request.user) else []
        )
        current_branch_id = request.GET.get("branch")

        return render(
            request,
            "inventory/adjustments.html",
            {
                "adjustments": page_obj.object_list,
                "page_obj": page_obj,
                "products": products,
                "branches": branches,
                "current_branch_id": current_branch_id,
            },
        )

    def post(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_adjustments_page", "can_manage_adjustments"
        )
        if permission_redirect:
            return permission_redirect

        product_id = request.POST.get("product")
        adjustment_type = request.POST.get("adjustment_type")
        quantity = int(request.POST.get("quantity", 0))
        reason = request.POST.get("reason")

        if adjustment_type == "decrease":
            quantity = -abs(quantity)
        else:
            quantity = abs(quantity)

        # Global access checks to target different branches
        if has_global_inventory_access(request.user):
            branch_id = request.POST.get("branch")
            if not branch_id:
                messages.error(request, "Please select a branch.")
                return redirect("inventory-adjustments-page")
            branch = get_object_or_404(Branch, id=branch_id)
        else:
            branch = getattr(request.user, "branch", None)
            if not branch:
                messages.error(request, "You are not assigned to any branch.")
                return redirect("inventory-adjustments-page")

        product = Product.objects.get(id=product_id)
        adj = InventoryAdjustment.objects.create(
            product=product,
            branch=branch,
            adjustment_type=adjustment_type,
            quantity=quantity,
            reason=reason,
            created_by=request.user,
        )
        AuditLog.log(request.user, f"adjustment {adjustment_type}", adj)
        if not getattr(request.user, "is_admin", False):
            notify_inventory_admins(
                request.user,
                "inventory_action",
                f"Inventory adjustment by {request.user.username}",
                f"{request.user.username} created a {adjustment_type} adjustment of {abs(quantity)} for {product.name}.",
                target_url="/inventory/adjustments/",
            )
        return redirect("inventory-adjustments-page")


class InventoryAdjustmentAPI(ListCreateAPIView):
    """
    DRF API endpoint listing and recording inventory adjustments.
    Requires authentication, applying branch parameters isolation.
    """
    serializer_class = InventoryAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(InventoryAdjustment.objects.all(), self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            branch=getattr(self.request.user, "branch", None),
        )
