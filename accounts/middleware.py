import logging

from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class InventoryAccessMiddleware:
    """
    Middleware that ensures Inventory Users use the dedicated InventoryUser model,
    and isolates them from Project Management.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Check standard user
        from django.contrib.auth.models import AnonymousUser

        is_pm_user = (
            hasattr(request, "user")
            and request.user.is_authenticated
            and not isinstance(request.user, AnonymousUser)
        )

        # Check explicit inventory session
        inv_user_id = request.session.get("inv_user_id")
        inv_user = None

        if inv_user_id:
            try:
                from inventory.models import InventoryUser

                inv_user = InventoryUser.objects.get(id=inv_user_id)
                # If no PM user is logged in, use the inventory user as the primary user object
                # CRITICAL: Never override request.user for /admin/ as it breaks Django Admin
                if not is_pm_user and not path.startswith("/admin/"):
                    request.user = inv_user
                    is_pm_user = False  # It's an inventory user now
            except Exception:
                pass

        # 1. Provide Context for Inventory Paths
        # CRITICAL: Do NOT override request.user for /admin/ paths, as Django Admin expects standard User model
        if (
            path.startswith("/inventory/") or path.startswith("/api/inventory/") or path.startswith("/accounts/inventory/")
        ) and not path.startswith("/admin/"):
            if inv_user:
                # Override request.user to prevent rewriting 100+ lines of codebase!
                request.user = inv_user
                user_to_check = inv_user
            elif is_pm_user and getattr(request.user, "can_access_inventory", False):
                # Standard PM user with inventory access, let them pass!
                user_to_check = request.user
            else:
                # Block PM users and anonymous users
                return redirect("accounts:login")

            if not user_to_check.is_admin:
                page_permissions = [
                    (
                        "/inventory/main/adjustments/",
                        "can_access_adjustments_page",
                        "can_manage_adjustments",
                    ),
                    (
                        "/inventory/main/serials/",
                        "can_access_serials_page",
                        "can_manage_serials",
                    ),
                    (
                        "/inventory/main/limits/",
                        "can_access_limits_page",
                        "can_manage_limits",
                    ),
                    (
                        "/inventory/main/alerts/",
                        "can_access_alerts_page",
                        "can_manage_alerts",
                    ),
                    (
                        "/inventory/main/rentals/",
                        "can_access_rentals_page",
                        "can_manage_rentals",
                    ),
                    ("/inventory/main/shortage/", "can_access_shortage_page", None),
                ]
                for page_prefix, access_field, manage_field in page_permissions:
                    if path.startswith(page_prefix):
                        if not getattr(user_to_check, access_field, True):
                            messages.error(
                                request,
                                "You do not have access to this inventory page.",
                            )
                            return redirect("/inventory/dashboard/")
                        if (
                            request.method == "POST"
                            and manage_field
                            and not getattr(user_to_check, manage_field, True)
                        ):
                            messages.error(
                                request,
                                "You do not have permission to manage actions on this page.",
                            )
                            return redirect("/inventory/dashboard/")

                if path.startswith(
                    "/inventory/main/shortage/export/"
                ) and not getattr(user_to_check, "can_manage_shortage_exports", True):
                    messages.error(
                        request,
                        "You do not have permission to export shortage data.",
                    )
                    return redirect("/inventory/main/shortage/")
                api_permissions = [
                    (
                        "/inventory/main/adjustments/",
                        "can_access_adjustments_page",
                        "can_manage_adjustments",
                    ),
                    (
                        "/inventory/main/serials/",
                        "can_access_serials_page",
                        "can_manage_serials",
                    ),
                    (
                        "/inventory/main/limits/",
                        "can_access_limits_page",
                        "can_manage_limits",
                    ),
                    (
                        "/inventory/main/alerts/",
                        "can_access_alerts_page",
                        "can_manage_alerts",
                    ),
                ]
                for api_prefix, access_field, manage_field in api_permissions:
                    if path.startswith(api_prefix):
                        if not getattr(user_to_check, access_field, True):
                            messages.error(
                                request,
                                "You do not have access to this inventory API.",
                            )
                            return redirect("/inventory/dashboard/")
                        if (
                            request.method != "GET"
                            and manage_field
                            and not getattr(user_to_check, manage_field, True)
                        ):
                            messages.error(
                                request,
                                "You do not have permission to manage this inventory API action.",
                            )
                            return redirect("/inventory/dashboard/")

        # 2. Block Inventory Users from PM
        if inv_user and not is_pm_user:
            allowed = [
                "/inventory/",
                "/api/inventory/",
                "/admin/",
                "/accounts/",
                "/media/",
                "/static/",
            ]
            if not any(path.startswith(prefix) for prefix in allowed):
                return redirect("/inventory/dashboard/")

        response = self.get_response(request)
        return response
