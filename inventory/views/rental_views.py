from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from products.models import Product
from stock.models import StockEntry
from ..models import Rental, BranchStock, Branch
from ..notifications import notify_inventory_admins
from ..utils import get_isolated_products, has_global_inventory_access

"""
This module processes equipment rentals tracking, stock-out actions, and return registers.
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


class RentalManagementView(View):
    """
    View class displaying active and overdue rentals, and capturing rental checkout / return.
    Checks out quantity by generating a StockEntry (entry_type='out') and registers returns
    with a corresponding StockEntry (entry_type='in').
    """
    def get(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_rentals_page"
        )
        if permission_redirect:
            return permission_redirect

        products_qs = get_isolated_products(request.user)
        isolated_product_ids = products_qs.values_list("id", flat=True)

        rentals = (
            Rental.objects.filter(product__in=isolated_product_ids)
            .select_related("product")
            .order_by("-created_at")
        )
        overdue_rentals = rentals.filter(
            status="active", return_date__lt=timezone.now().date()
        )

        user_branch = getattr(request.user, "branch", None)
        product_availability = {}
        for product in products_qs:
            bs = BranchStock.objects.filter(product=product, branch=user_branch).first()
            available = bs.current_quantity if bs else 0
            product.available = available
            product_availability[product.id] = available

        available_products = [p for p in products_qs if p.available > 0]
        branches = (
            Branch.objects.all() if has_global_inventory_access(request.user) else []
        )

        return render(
            request,
            "inventory/rentals.html",
            {
                "rentals": rentals,
                "overdue_rentals": overdue_rentals,
                "products": available_products,
                "product_availability": product_availability,
                "branches": branches,
            },
        )

    def post(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_rentals_page", "can_manage_rentals"
        )
        if permission_redirect:
            return permission_redirect

        action = request.POST.get("action")
        if action == "create":
            product_id = request.POST.get("product")
            quantity = int(request.POST.get("quantity"))
            rented_to = request.POST.get("rented_to")
            reason = request.POST.get("reason")
            rental_date = request.POST.get("rental_date")
            rental_time = request.POST.get("rental_time")
            return_date = request.POST.get("return_date") or None
            product = Product.objects.get(id=product_id)

            if has_global_inventory_access(request.user):
                branch_id = request.POST.get("branch")
                if not branch_id:
                    messages.error(request, "Please select a branch.")
                    return redirect("rental-management")
                branch = get_object_or_404(Branch, id=branch_id)
            else:
                branch = getattr(request.user, "branch", None)
                if not branch:
                    messages.error(request, "You are not assigned to any branch.")
                    return redirect("rental-management")

            # Validate stock availability
            bs = BranchStock.objects.filter(product=product, branch=branch).first()
            available_quantity = bs.current_quantity if bs else 0
            if quantity > available_quantity:
                messages.error(
                    request,
                    f"Cannot rent {quantity} units of {product.name}. Only {available_quantity} available.",
                )
                return redirect("rental-management")

            # Create Stock Entry out transaction
            StockEntry.objects.create(
                product=product,
                quantity=quantity,
                branch=branch,
                entry_type="out",
                created_by=request.user,
                description=f"Rental to {rented_to}",
            )
            Rental.objects.create(
                product=product,
                branch=branch,
                quantity=quantity,
                rented_to=rented_to,
                reason=reason,
                rental_date=rental_date,
                rental_time=rental_time,
                return_date=return_date,
                status="active",
                created_by=request.user,
            )
            messages.success(
                request, f"Rented {quantity} of {product.name} to {rented_to}."
            )
            if not getattr(request.user, "is_admin", False):
                notify_inventory_admins(
                    request.user,
                    "inventory_action",
                    f"Rental created by {request.user.username}",
                    f"{request.user.username} rented {quantity} unit(s) of {product.name} to {rented_to}.",
                    target_url="/inventory/rentals/",
                )
        elif action == "return":
            rental_id = request.POST.get("rental_id")
            rental = Rental.objects.get(id=rental_id)
            if rental.status == "active":
                # Create Stock Entry in transaction (stock restored)
                StockEntry.objects.create(
                    product=rental.product,
                    branch=rental.branch,
                    quantity=rental.quantity,
                    entry_type="in",
                    created_by=request.user,
                    description=f"Rental Return from {rental.rented_to}",
                )
                rental.status = "returned"
                rental.save()
                messages.success(
                    request, f"Rental for {rental.product.name} marked as returned."
                )
                if not getattr(request.user, "is_admin", False):
                    notify_inventory_admins(
                        request.user,
                        "inventory_action",
                        f"Rental returned by {request.user.username}",
                        f"{request.user.username} marked rental #{rental.id} for {rental.product.name} as returned.",
                        target_url="/inventory/rentals/",
                    )
        return redirect("rental-management")
