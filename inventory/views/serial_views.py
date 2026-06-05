from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.shortcuts import redirect, render
from django.views import View
from rest_framework import filters
from rest_framework.generics import ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from products.models import Product
from ..models import SerialNumber
from ..serializers import SerialNumberSerializer
from ..notifications import notify_inventory_admins
from ..utils import get_isolated_products, filter_by_branch

"""
This module processes serial number registers search queries, sync commands, and REST APIs.
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


class SerialNumbersPageView(View):
    """
    View class displaying serial registers, supporting search queries,
    and triggering batch synchronization commands on POST.
    """
    def get(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_serials_page"
        )
        if permission_redirect:
            return permission_redirect

        search_query = request.GET.get("search", "")
        products = get_isolated_products(request.user)
        serials = filter_by_branch(
            SerialNumber.objects.all(), request.user
        ).select_related("product")
        if search_query:
            serials = serials.filter(
                models.Q(serial_number__icontains=search_query)
                | models.Q(product__name__icontains=search_query)
                | models.Q(product__brand__icontains=search_query)
                | models.Q(product__sku__icontains=search_query)
            )
        serials = serials.order_by("-created_at")
        paginator = Paginator(serials, 50)
        page_number = request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        products_with_serials = products.exclude(serial_number__isnull=True).exclude(
            serial_number=""
        )
        return render(
            request,
            "inventory/serials.html",
            {
                "serials": page_obj.object_list,
                "page_obj": page_obj,
                "products_with_serials": products_with_serials,
                "search_query": search_query,
            },
        )

    def post(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_serials_page", "can_manage_serials"
        )
        if permission_redirect:
            return permission_redirect

        products_with_serials = Product.objects.exclude(
            serial_number__isnull=True
        ).exclude(serial_number="")
        created_count = 0
        updated_count = 0
        for product in products_with_serials:
            existing_serial = SerialNumber.objects.filter(
                serial_number=product.serial_number
            ).first()
            if existing_serial:
                if existing_serial.product != product:
                    existing_serial.product = product
                    existing_serial.save()
                    updated_count += 1
            else:
                SerialNumber.objects.create(
                    serial_number=product.serial_number,
                    product=product,
                    branch=getattr(request.user, "branch", None),
                    status="available",
                )
                created_count += 1
        messages.success(
            request,
            f"Serial numbers synced! Created: {created_count}, Updated: {updated_count}",
        )
        if not getattr(request.user, "is_admin", False) and (created_count or updated_count):
            notify_inventory_admins(
                request.user,
                "inventory_action",
                f"Serial sync by {request.user.username}",
                f"{request.user.username} synced serials. Created: {created_count}, Updated: {updated_count}.",
                target_url="/inventory/serials/",
            )
        return redirect("inventory-serials-page")


class SerialNumberPagination(PageNumberPagination):
    """Custom pagination layout for serial numbers listings."""
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class SerialNumbersAPI(ListCreateAPIView):
    """
    DRF API endpoint listing and creating Serial Numbers.
    """
    serializer_class = SerialNumberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(SerialNumber.objects.all(), self.request.user)

    filter_backends = [filters.SearchFilter]
    search_fields = ["serial_number", "product__name", "product__brand", "product__sku"]
    pagination_class = SerialNumberPagination
