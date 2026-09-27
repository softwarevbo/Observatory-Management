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
        
        # If superuser or admin, grant access immediately
        if request.user.is_admin:
            return view_func(request, *args, **kwargs)

        # Check if project context is available in arguments
        pk = kwargs.get("pk") or kwargs.get("project_id") or kwargs.get("project_pk")
        if pk:
            from .models import Project
            try:
                project = Project.objects.get(pk=pk)
                if not project.is_manager(request.user):
                    messages.error(
                        request, "You do not have manager permission for this project."
                    )
                    return redirect("tasks:project_detail", pk=pk)
            except (Project.DoesNotExist, ValueError):
                pass
        
        return view_func(request, *args, **kwargs)

    return wrapper
