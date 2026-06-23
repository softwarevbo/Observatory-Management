from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

"""
This module defines authorization decorators for Inventory Management view views.
Restricts routes to super admins, branch admins, or users with specific permission flags.
"""

def super_admin_required(view_func):
    """
    Decorator requiring the user to have is_super_admin set to True.
    Otherwise redirects to dashboard-page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not getattr(request.user, "is_super_admin", False):
            messages.error(
                request, "You need Super Admin privileges to access this page."
            )
            return redirect("dashboard-page")
        return view_func(request, *args, **kwargs)

    return wrapper


def branch_admin_required(view_func):
    """
    Decorator requiring the user to have is_branch_admin or is_super_admin set to True.
    Otherwise redirects to dashboard-page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (getattr(request.user, "is_branch_admin", False) or getattr(request.user, "is_super_admin", False)):
            messages.error(
                request, "You need Admin privileges to access this page."
            )
            return redirect("dashboard-page")
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

            # Admins always have access
            if getattr(request.user, "is_super_admin", False) or getattr(request.user, "is_branch_admin", False):
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
