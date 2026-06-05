from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from products.models import Product
from tasks.decorators import admin_required
from ..models import QuantityLimit, StandardLimit, Branch
from ..serializers import QuantityLimitSerializer
from ..notifications import notify_inventory_admins
from ..utils import get_isolated_products, filter_by_branch, has_global_inventory_access

"""
This module processes threshold configurations, default global boundaries, and APIs.
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


def set_standard_limit(request):
    """
    Sets a global default limit threshold.
    Applies the set standard limit count to products that do not have custom quantity limits assigned.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method == "POST":
        limit = request.POST.get("standard_limit")
        if limit and limit.isdigit():
            obj, created = StandardLimit.objects.get_or_create(
                id=1, defaults={"value": int(limit)}
            )
            if not created:
                obj.value = int(limit)
                obj.save()
            products_without_limit = Product.objects.filter(quantity_limit__isnull=True)
            for product in products_without_limit:
                QuantityLimit.objects.create(
                    product=product,
                    limit_quantity=int(limit),
                    is_active=True,
                    created_by=request.user,
                )
            messages.success(
                request,
                f"Standard limit set to {limit}. Applied to {products_without_limit.count()} products.",
            )
        else:
            messages.error(request, "Please enter a valid limit.")
    return redirect("inventory-limits-page")


@method_decorator(admin_required, name="dispatch")
class QuantityLimitsPageView(View):
    """
    View class displaying active low-stock triggers list by branch.
    Allows creating or updating limit limits.
    """
    def get(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_limits_page"
        )
        if permission_redirect:
            return permission_redirect

        products_qs = get_isolated_products(request.user)
        limits = filter_by_branch(QuantityLimit.objects.all(), request.user)
        products = products_qs.values("id", "name", "serial_number")

        try:
            standard_limit = StandardLimit.objects.get(id=1).value
        except StandardLimit.DoesNotExist:
            standard_limit = None

        branches = (
            Branch.objects.all() if has_global_inventory_access(request.user) else []
        )
        return render(
            request,
            "inventory/limits.html",
            {
                "limits": limits,
                "products": list(products),
                "standard_limit": standard_limit,
                "branches": branches,
            },
        )

    def post(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_limits_page", "can_manage_limits"
        )
        if permission_redirect:
            return permission_redirect

        product_id = request.POST.get("product")
        limit_quantity = request.POST.get("limit_quantity")
        is_active = request.POST.get("is_active") == "on"

        if has_global_inventory_access(request.user):
            branch_id = request.POST.get("branch")
            if not branch_id:
                messages.error(request, "Please select a branch.")
                return redirect("inventory-limits-page")
            branch = get_object_or_404(Branch, id=branch_id)
        else:
            branch = getattr(request.user, "branch", None)
            if not branch:
                messages.error(request, "You are not assigned to any branch.")
                return redirect("inventory-limits-page")

        product = Product.objects.get(id=product_id)
        limit, created = QuantityLimit.objects.update_or_create(
            product=product,
            branch=branch,
            defaults={
                "limit_quantity": limit_quantity,
                "is_active": is_active,
                "created_by": request.user,
            },
        )

        messages.success(
            request,
            f"Quantity limit {'set' if created else 'updated'} for {product.name}",
        )
        if not getattr(request.user, "is_admin", False):
            notify_inventory_admins(
                request.user,
                "inventory_action",
                f"Quantity limit update by {request.user.username}",
                f"{request.user.username} set limit {limit_quantity} for {product.name}. Active: {is_active}.",
                target_url="/inventory/limits/",
            )
        return redirect("inventory-limits-page")


class QuantityLimitsAPI(ListCreateAPIView):
    """
    DRF API endpoint listing and recording product limits.
    """
    serializer_class = QuantityLimitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(QuantityLimit.objects.all(), self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            branch=getattr(self.request.user, "branch", None),
        )


class QuantityLimitDetailAPI(RetrieveUpdateDestroyAPIView):
    """
    DRF API endpoint displaying, modifying or removing specific product limits.
    """
    queryset = QuantityLimit.objects.all()
    serializer_class = QuantityLimitSerializer
    permission_classes = [IsAuthenticated]
