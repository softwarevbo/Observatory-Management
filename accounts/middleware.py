import logging

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.shortcuts import redirect

from .rbac import (
    get_canonical_role,
    get_default_redirect_for_role,
    has_permission,
    PERMISSION_INVENTORY_ACCESS,
    PERMISSION_INVENTORY_USER_MANAGE,
    PERMISSION_PROJECT_ACCESS,
    PERMISSION_PROJECT_USER_MANAGE,
    PERMISSION_TELESCOPE_ACCESS,
    PERMISSION_TELESCOPE_USER_MANAGE,
    ROLE_ROOT,
)

logger = logging.getLogger(__name__)

"""
RBAC Access Middleware enforcing module-level access control.
Isolates Project Management, Telescope Management, and Inventory Management routes.
"""


class RBACAccessMiddleware:
    """
    Middleware enforcing strict module-level authorization:
    - Project Management: /tasks/*, /files/*, /finance/*, /chat/*, /resource-hub/*, /
    - Telescope Management: /telescope/*
    - Inventory Management: /inventory/*, /api/inventory/*
    - User Management: /accounts/users/*
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Exempt paths (Static, media, favicon, error pages, auth entry points, root landing page)
        exempt_paths = [
            "/",
            "/iia-logo.jpg",
            "/background.png",
        ]
        exempt_prefixes = [
            "/static/",
            "/media/",
            "/favicon.ico",
            "/404/",
            "/__debug__/",
            "/accounts/login/",
            "/accounts/telescope_login/",
            "/accounts/inventory_login/",
            "/accounts/logout/",
        ]

        if path in exempt_paths or any(path.startswith(prefix) for prefix in exempt_prefixes):
            return self.get_response(request)

        # Allow Django admin for superusers/staff
        if path.startswith("/admin/") or path.startswith("/Iiap2026/"):
            return self.get_response(request)


        # Check standard user authentication
        is_pm_user = (
            hasattr(request, "user")
            and request.user.is_authenticated
            and not isinstance(request.user, AnonymousUser)
        )

        # Retrieve inventory user ID or telescope user ID from session if present
        inv_user_id = request.session.get("inv_user_id")
        tele_user_id = request.session.get("tele_user_id")
        inv_user = None
        tele_user = None

        if inv_user_id:
            try:
                from inventory.models import InventoryUser

                inv_user = InventoryUser.objects.get(id=inv_user_id)
                if not is_pm_user:
                    request.user = inv_user
            except Exception:
                pass

        if tele_user_id:
            try:
                from telescope.models import TelescopeUser

                tele_user = TelescopeUser.objects.get(id=tele_user_id)
                if not is_pm_user and not inv_user:
                    request.user = tele_user
            except Exception:
                pass

        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            # Unauthenticated users accessing protected paths redirect to login
            if path.startswith("/api/"):
                return JsonResponse({"error": "Authentication required."}, status=401)
            return redirect(f"/accounts/login/?next={path}")

        canonical_role = get_canonical_role(user)

        # ─── 1. TELESCOPE MODULE AUTHORIZATION ──────────────────────────────────
        if path.startswith("/telescope/") or path.startswith("/telescopecontrol/") or path.startswith("/api/telescope/"):
            if not has_permission(user, PERMISSION_TELESCOPE_ACCESS):
                if path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Access Denied: Telescope Management restriction."},
                        status=403,
                    )
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access Telescope Management.",
                )
                return redirect(get_default_redirect_for_role(user))

            return self.get_response(request)

        # ─── 2. INVENTORY MODULE AUTHORIZATION ──────────────────────────────────
        if (
            path.startswith("/inventory/")
            or path.startswith("/inventorymanagement/")
            or path.startswith("/api/inventory/")
            or path.startswith("/accounts/inventory/")
        ):
            if inv_user:
                request.user = inv_user
                user_to_check = inv_user
            else:
                user_to_check = user

            if not has_permission(user_to_check, PERMISSION_INVENTORY_ACCESS):
                if path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Access Denied: Inventory Management restriction."},
                        status=403,
                    )
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access Inventory Management.",
                )
                return redirect(get_default_redirect_for_role(user_to_check))

            # Granular Inventory Sub-Page Checks for non-admin staff
            if not getattr(user_to_check, "is_admin", False) and canonical_role != ROLE_ROOT:
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

            return self.get_response(request)

        # ─── 3. USER MANAGEMENT AUTHORIZATION ────────────────────────────────────
        if path.startswith("/accounts/users/"):
            can_pm_manage = has_permission(user, PERMISSION_PROJECT_USER_MANAGE)
            can_tm_manage = has_permission(user, PERMISSION_TELESCOPE_USER_MANAGE)
            can_im_manage = has_permission(user, PERMISSION_INVENTORY_USER_MANAGE)

            if not (can_pm_manage or can_tm_manage or can_im_manage):
                if path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Access Denied: User Management permission required."},
                        status=403,
                    )
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access User Management.",
                )
                return redirect(get_default_redirect_for_role(user))

            return self.get_response(request)

        # ─── 4. PROJECT MANAGEMENT AUTHORIZATION ─────────────────────────────────
        pm_routes = [
            "/projectmanagement/",
            "/dashboard/",
            "/tasks/",
            "/projects/",
            "/files/",
            "/finance/",
            "/chat/",
            "/resource-hub/",
            "/bugs/",
            "/releases/",
            "/requirements/",
            "/modules/",
            "/test-cases/",
            "/knowledge-base/",
            "/notifications/",
            "/calendar/",
            "/reports/",
            "/report-center/",
            "/audit-logs/",
            "/trash/",
        ]
        is_pm_route = any(path.startswith(prefix) for prefix in pm_routes)

        if is_pm_route:
            if not has_permission(user, PERMISSION_PROJECT_ACCESS):
                if path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Access Denied: Project Management restriction."},
                        status=403,
                    )
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access Project Management.",
                )
                return redirect(get_default_redirect_for_role(user))

        return self.get_response(request)


# Backwards compatibility alias
InventoryAccessMiddleware = RBACAccessMiddleware
