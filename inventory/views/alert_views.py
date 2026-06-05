from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Alert
from ..serializers import AlertSerializer
from ..notifications import notify_inventory_admins
from ..utils import filter_by_branch

"""
This module processes stock level alerts tracking, acknowledgement, resolution, and APIs.
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


class AlertsPageView(View):
    """
    View class listing active alerts by branch and processing acknowledge/resolve requests.
    """
    def get(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_alerts_page"
        )
        if permission_redirect:
            return permission_redirect

        alerts = filter_by_branch(
            Alert.objects.all(), request.user, "product__branch"
        ).order_by("-created_at")
        paginator = Paginator(alerts, 50)
        page_number = request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        return render(
            request,
            "inventory/alerts.html",
            {"alerts": page_obj.object_list, "page_obj": page_obj},
        )

    def post(self, request):
        permission_redirect = _inventory_permission_redirect(
            request, "can_access_alerts_page", "can_manage_alerts"
        )
        if permission_redirect:
            return permission_redirect

        alert_id = request.POST.get("alert_id")
        action = request.POST.get("action")
        alert = get_object_or_404(Alert, id=alert_id)
        if action == "acknowledge":
            alert.status = "acknowledged"
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user
            alert.save()
            messages.success(request, "Alert acknowledged")
        elif action == "resolve":
            alert.status = "resolved"
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            messages.success(request, "Alert resolved")

        if not getattr(request.user, "is_admin", False):
            notify_inventory_admins(
                request.user,
                "inventory_action",
                f"Alert action by {request.user.username}",
                f'{request.user.username} performed "{action}" on alert #{alert.id} for {alert.product.name}.',
                target_url="/inventory/alerts/",
            )
        return redirect("inventory-alerts-page")


class AlertsAPI(ListCreateAPIView):
    """
    DRF API endpoint listing stock levels alerts by branch constraints.
    """
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(
            Alert.objects.all(), self.request.user, "product__branch"
        )


class AlertDetailAPI(RetrieveUpdateDestroyAPIView):
    """
    DRF API endpoint displaying, modifying or removing specific alerts.
    """
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]


class AcknowledgeAlertAPI(APIView):
    """
    API controller marking specific alerts as acknowledged by current user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.status = "acknowledged"
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user
            alert.save()
            return Response({"status": "success", "message": "Alert acknowledged"})
        except Alert.DoesNotExist:
            return Response(
                {"status": "error", "message": "Alert not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class ResolveAlertAPI(APIView):
    """
    API controller marking specific alerts as resolved by current user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.status = "resolved"
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            return Response({"status": "success", "message": "Alert resolved"})
        except Alert.DoesNotExist:
            return Response(
                {"status": "error", "message": "Alert not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
