import logging

from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

"""
This module defines Django Custom Middleware classes.
Middleware is a framework of hooks into Django's request/response processing.
It's a light, low-level 'plugin' system for globally altering Django's input or output.

Here we implement `InventoryAccessMiddleware` to:
1. Detect and isolate standard Project Management (PM) users vs Inventory-specific users.
2. Dynamically substitute the logged-in User object with `InventoryUser` for inventory paths
   without breaking django admin.
3. Validate user permissions on specific inventory paths (such as adjustments, limits, rentals, shortage exports).
"""

class InventoryAccessMiddleware:
    """
    Middleware that ensures Inventory Users use the dedicated InventoryUser model,
    and isolates them from Project Management pages.
    """

    def __init__(self, get_response):
        """
        One-time configuration and initialization.
        get_response is the next middleware or view callable in the chain.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Code to be executed for each request before the view (and later middleware) are called.
        """
        path = request.path

        # Check if the user is a authenticated standard User (PM User)
        from django.contrib.auth.models import AnonymousUser

        is_pm_user = (
            hasattr(request, "user")
            and request.user.is_authenticated
            and not isinstance(request.user, AnonymousUser)
        )

        # Retrieve inventory user ID from session storage if logged in via InventoryLogin view
        inv_user_id = request.session.get("inv_user_id")
        inv_user = None

        if inv_user_id:
            try:
                from inventory.models import InventoryUser

                inv_user = InventoryUser.objects.get(id=inv_user_id)
                # If no PM user is logged in, use the inventory user as the primary user object.
                # CRITICAL: Never override request.user for /admin/ as it breaks Django Admin authentication.
                if not is_pm_user and not path.startswith("/admin/"):
                    request.user = inv_user
                    is_pm_user = False  # It's an inventory user now
            except Exception:
                pass

        # ─── 1. Provide Context & Auth Checks for Inventory Paths ────────────────────
        # Match routes starting with /inventory/, /api/inventory/, or /accounts/inventory/
        if (
            path.startswith("/inventory/") or path.startswith("/api/inventory/") or path.startswith("/accounts/inventory/")
        ) and not path.startswith("/admin/"):
            if inv_user:
                # Override request.user to prevent rewriting 100+ lines of inventory codebase!
                # This makes the inventory code treat this session user as the request.user.
                request.user = inv_user
                user_to_check = inv_user
            elif is_pm_user and getattr(request.user, "can_access_inventory", False):
                # Standard PM user with explicit inventory access, let them pass!
                user_to_check = request.user
            else:
                # Block PM users without permission and anonymous users: redirect to login
                return redirect("accounts:login")

            # Check granular page permissions for non-admin users
            if not user_to_check.is_admin:
                # A list of tuples containing (URL prefix, access permission field name, manage permission field name)
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
                
                # Iterate and assert matching prefixes
                for page_prefix, access_field, manage_field in page_permissions:
                    if path.startswith(page_prefix):
                        # Verify the user has the read permission flag
                        if not getattr(user_to_check, access_field, True):
                            messages.error(
                                request,
                                "You do not have access to this inventory page.",
                            )
                            return redirect("/inventory/dashboard/")
                        
                        # If making a POST request (modification), verify they have the manage permission flag
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

                # Check shortage export permissions
                if path.startswith(
                    "/inventory/main/shortage/export/"
                ) and not getattr(user_to_check, "can_manage_shortage_exports", True):
                    messages.error(
                        request,
                        "You do not have permission to export shortage data.",
                    )
                    return redirect("/inventory/main/shortage/")
                
                # Repeat permission checking for API endpoints prefixing adjustments/serials/limits/alerts
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
                            request.method != "GET" # POST, PUT, DELETE operations
                            and manage_field
                            and not getattr(user_to_check, manage_field, True)
                        ):
                            messages.error(
                                request,
                                "You do not have permission to manage this inventory API action.",
                            )
                            return redirect("/inventory/dashboard/")

        # ─── 2. Block Inventory-Only Users from Project Management (PM) ─────────────
        # If the user is logged in as an inventory user but NOT as a PM user,
        # redirect them to the inventory dashboard if they attempt to access PM urls.
        if inv_user and not is_pm_user:
            allowed = [
                "/inventory/",
                "/api/inventory/",
                "/admin/",
                "/accounts/",
                "/media/",
                "/static/",
                "/__debug__/",
            ]
            if not any(path.startswith(prefix) for prefix in allowed):
                return redirect("/inventory/dashboard/")

        # ─── 3. Block Telescope-Only Users from Project Management (PM) ─────────────
        # If the user is logged in as a standard user but does not have PM access,
        # redirect them to the telescope dashboard if they attempt to access PM urls.
        if (
            is_pm_user
            and not getattr(request.user, "is_superuser", False)
            and not getattr(request.user, "is_admin", False)
            and not getattr(request.user, "can_access_pm", False)
        ):
            allowed = [
                "/telescope/",
                "/inventory/",
                "/api/inventory/",
                "/accounts/",
                "/media/",
                "/static/",
                "/__debug__/",
            ]
            if not any(path.startswith(prefix) for prefix in allowed) and path != "/":
                return redirect("telescope:dashboard")

        # Process the request normally and return the generated response
        response = self.get_response(request)
        return response

