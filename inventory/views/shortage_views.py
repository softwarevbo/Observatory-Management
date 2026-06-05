import csv
import io
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from ..models import QuantityLimit, StandardLimit, BranchStock
from ..utils import get_isolated_products

"""
This module processes shortage analysis reports and export workflows.
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


def inventory_shortage_view(request):
    """
    Renders the inventory shortages panel.
    Calculates shortages per product comparing current BranchStock levels against 
    custom QuantityLimit thresholds or StandardLimit fallbacks.
    """
    permission_redirect = _inventory_permission_redirect(
        request, "can_access_shortage_page"
    )
    if permission_redirect:
        return permission_redirect

    products = get_isolated_products(request.user)
    products_list = [{"id": p.id, "name": p.name} for p in products]

    try:
        standard_limit = StandardLimit.objects.get(id=1).value
    except StandardLimit.DoesNotExist:
        standard_limit = None

    shortage_items = []
    user_branch = getattr(request.user, "branch", None)
    for product in products:
        bs = BranchStock.objects.filter(product=product, branch=user_branch).first()
        current_quantity = bs.current_quantity if bs else 0
        try:
            limit_obj = QuantityLimit.objects.get(product=product, is_active=True)
            limit = limit_obj.limit_quantity
        except QuantityLimit.DoesNotExist:
            limit = standard_limit

        if limit is not None and current_quantity <= limit:
            qty_to_buy = abs(limit - current_quantity)
            shortage_items.append(
                {
                    "product": {"id": product.id, "name": product.name},
                    "current_quantity": current_quantity,
                    "limit": limit,
                    "qty_to_buy": qty_to_buy,
                }
            )
    return render(
        request,
        "inventory/shortage.html",
        {"shortage_items": shortage_items, "products": products_list},
    )


def inventory_shortage_export_csv(request):
    """
    Exports a spreadsheet CSV representation of the active shortages.
    """
    permission_redirect = _inventory_permission_redirect(
        request, "can_access_shortage_page"
    )
    if permission_redirect:
        return permission_redirect

    products = get_isolated_products(request.user)
    try:
        standard_limit = StandardLimit.objects.get(id=1).value
    except StandardLimit.DoesNotExist:
        standard_limit = None

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="inventory_shortage.csv"'
    writer = csv.writer(response)
    writer.writerow(["Product", "Current Quantity", "Limit", "Quantity to Buy"])

    user_branch = getattr(request.user, "branch", None)
    for product in products:
        bs = BranchStock.objects.filter(product=product, branch=user_branch).first()
        current_quantity = bs.current_quantity if bs else 0
        try:
            limit_obj = QuantityLimit.objects.get(product=product, is_active=True)
            limit = limit_obj.limit_quantity
        except QuantityLimit.DoesNotExist:
            limit = standard_limit
        if limit is not None and current_quantity <= limit:
            writer.writerow(
                [product.name, current_quantity, limit, abs(limit - current_quantity)]
            )
    return response


def inventory_shortage_export_pdf(request):
    """
    Exports a PDF document using xhtml2pdf containing the active shortages list.
    """
    permission_redirect = _inventory_permission_redirect(
        request, "can_access_shortage_page"
    )
    if permission_redirect:
        return permission_redirect

    products = get_isolated_products(request.user)
    try:
        standard_limit = StandardLimit.objects.get(id=1).value
    except StandardLimit.DoesNotExist:
        standard_limit = None

    shortage_items = []
    user_branch = getattr(request.user, "branch", None)
    for product in products:
        bs = BranchStock.objects.filter(product=product, branch=user_branch).first()
        current_quantity = bs.current_quantity if bs else 0
        try:
            limit_obj = QuantityLimit.objects.get(product=product, is_active=True)
            limit = limit_obj.limit_quantity
        except QuantityLimit.DoesNotExist:
            limit = standard_limit
        if limit is not None and current_quantity <= limit:
            shortage_items.append(
                {
                    "product": product,
                    "current_quantity": current_quantity,
                    "limit": limit,
                    "qty_to_buy": abs(limit - current_quantity),
                }
            )

    html_string = render_to_string(
        "inventory/shortage_pdf.html", {"shortage_items": shortage_items}
    )
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return HttpResponse("Error generating PDF", status=500)
