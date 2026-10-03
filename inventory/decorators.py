from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from accounts.rbac import has_permission, PERMISSION_INVENTORY_ACCESS, PERMISSION_INVENTORY_USER_MANAGE, PERMISSION_ADMIN_MANAGE, get_default_redirect_for_role


def super_admin_required(view_func):
    """
    Decorator requiring ROOT privileges.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not has_permission(request.user, PERMISSION_ADMIN_MANAGE):
            messages.error(
                request, "You need Root Admin privileges to access this page."
            )
            return redirect(get_default_redirect_for_role(request.user))
        return view_func(request, *args, **kwargs)

    return wrapper


def branch_admin_required(view_func):
    """
    Decorator requiring IM Admin or ROOT privileges.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (has_permission(request.user, PERMISSION_INVENTORY_USER_MANAGE) or getattr(request.user, "is_branch_admin", False) or getattr(request.user, "is_super_admin", False)):
            messages.error(
                request, "You need Admin privileges to access this page."
            )
            return redirect(get_default_redirect_for_role(request.user))
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_permission_required(perm_name):
    """
    Decorator for views that checks if the user has a specific permission attribute.
    Super Admins and Branch Admins bypass this constraint entirely.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")

            if not has_permission(request.user, PERMISSION_INVENTORY_ACCESS):
                messages.error(request, "Access Denied: You do not have permission to access Inventory Management.")
                return redirect(get_default_redirect_for_role(request.user))

            # Admins always have access
            if has_permission(request.user, PERMISSION_INVENTORY_USER_MANAGE) or getattr(request.user, "is_super_admin", False) or getattr(request.user, "is_branch_admin", False):
                return view_func(request, *args, **kwargs)

            # Check specific permission flag
            if getattr(request.user, perm_name, False):
                return view_func(request, *args, **kwargs)

            messages.error(
                request, f"You do not have permission to perform this action."
            )
            return redirect("dashboard-page")

        return wrapper

    return decorator
