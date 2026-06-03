from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.is_admin:
            messages.error(request, "You do not have permission to access this page.")
            return redirect("tasks:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper


def manager_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (request.user.is_admin or request.user.is_project_manager):
            messages.error(
                request, "You do not have permission to perform this action."
            )
            return redirect("tasks:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper
