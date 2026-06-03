from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ..models import Project, Task, ProjectModule, Requirement
from accounts.models import User
from ..utils.query_utils import get_visible_tasks_qs


@login_required
def tasks_for_project(request):
    project_id = request.GET.get("project_id")
    if not project_id:
        return JsonResponse({"tasks": []})
    tasks = (
        get_visible_tasks_qs(request.user, Task.objects.filter(project_id=project_id, parent_task__isnull=True, is_in_trash=False))
        .exclude(linked_bugs__is_in_trash=True)
        .values("id", "title", "task_id", "requirement_id")
        .order_by("title")
    )
    return JsonResponse({"tasks": list(tasks)})


@login_required
def project_modules_api(request):
    project_id = request.GET.get("project_id")
    if not project_id:
        return JsonResponse({"modules": [], "is_manager": False})
    project = get_object_or_404(Project, pk=project_id)
    is_manager = (
        project.managers.filter(pk=request.user.pk).exists() or request.user.is_admin
    )
    modules = (
        ProjectModule.objects.filter(project=project)
        .values("id", "name")
        .order_by("name")
    )
    return JsonResponse({"modules": list(modules), "is_manager": is_manager})


@login_required
def project_requirements_api(request):
    project_id = request.GET.get("project_id")
    if not project_id:
        return JsonResponse({"requirements": []})
    project = get_object_or_404(Project, pk=project_id)
    requirements = (
        Requirement.objects.filter(project=project, is_approved=True, is_in_trash=False)
        .values("id", "name", "req_id")
        .order_by("req_id")
    )
    return JsonResponse({"requirements": list(requirements)})


@login_required
def project_members_api(request):
    project_id = request.GET.get("project_id")
    if not project_id:
        return JsonResponse({"members": [], "can_assign": False})
    try:
        project = Project.objects.get(pk=project_id)
    except (Project.DoesNotExist, ValueError):
        return JsonResponse({"members": [], "can_assign": False})

    member_ids = list(project.members.values_list("pk", flat=True))
    member_ids.extend(project.managers.values_list("pk", flat=True))

    members = User.objects.filter(pk__in=member_ids, is_active=True).order_by(
        "first_name", "username"
    )
    data = [{"id": u.pk, "name": u.display_name} for u in members]
    
    can_assign = (
        request.user.is_superuser or 
        getattr(request.user, "is_admin", False) or 
        getattr(request.user, "is_project_manager", False) or 
        project.managers.filter(pk=request.user.pk).exists() or 
        project.project_incharge == request.user
    )
    return JsonResponse({"members": data, "can_assign": can_assign})

