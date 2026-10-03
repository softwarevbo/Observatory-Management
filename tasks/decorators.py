from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from accounts.rbac import has_permission, PERMISSION_PROJECT_USER_MANAGE, PERMISSION_PROJECT_ACCESS, get_default_redirect_for_role


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (has_permission(request.user, PERMISSION_PROJECT_USER_MANAGE) or getattr(request.user, "is_admin", False)):
            messages.error(request, "Access Denied: Admin permission required.")
            return redirect(get_default_redirect_for_role(request.user))
        return view_func(request, *args, **kwargs)

    return wrapper


def manager_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if not has_permission(request.user, PERMISSION_PROJECT_ACCESS):
            messages.error(request, "Access Denied: You do not have permission to access Project Management.")
            return redirect(get_default_redirect_for_role(request.user))

        # If superuser or PM admin, grant access immediately
        if has_permission(request.user, PERMISSION_PROJECT_USER_MANAGE) or getattr(request.user, "is_admin", False):
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
