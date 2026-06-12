from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from tasks.models import Project, AuditLog
from ..models import ProjectFile, FileCategory, DocumentAccessRight
from ..forms import FileCategoryForm

"""
This module processes folder node configurations, project categories API requests,
and custom file access overrides.
"""

@login_required
def file_access(request, pk):
    """
    Renders the permissions management page for a file.
    Permits managers and admins to assign or revoke explicit user access overrides.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    
    # Permission verification
    if not (
        request.user.is_admin
        or (pf.project and pf.project.managers.filter(pk=request.user.pk).exists())
    ):
        messages.error(request, "Only managers and admins can manage access rights.")
        return redirect("files:file_detail", pk=pk)
        
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            user_id = request.POST.get("user_id")
            if user_id:
                target_user = get_object_or_404(User, pk=user_id)
                ar, _ = DocumentAccessRight.objects.get_or_create(
                    file=pf, user=target_user
                )
                ar.can_view, ar.can_edit, ar.can_delete = (
                    request.POST.get("can_view") == "on",
                    request.POST.get("can_edit") == "on",
                    request.POST.get("can_delete") == "on",
                )
                ar.save()
                messages.success(
                    request, f"Access rights updated for {target_user.display_name}."
                )
        elif action == "remove":
            DocumentAccessRight.objects.filter(
                pk=request.POST.get("access_id")
            ).delete()
            messages.success(request, "Access right removed.")
        return redirect("files:file_access", pk=pk)
        
    return render(
        request,
        "files/file_access.html",
        {
            "file": pf,
            "access_rights": DocumentAccessRight.objects.filter(file=pf),
            "all_users": User.objects.filter(is_active=True),
        },
    )


@login_required
def project_categories_api(request):
    """
    JSON API returning directory folders list belonging to a project.
    Used for cascading parent folder selection options when creating folders/files.
    """
    project_id = request.GET.get("project_id")
    q_filter = (
        Q(project__managers=request.user)
        | Q(project__members=request.user)
        | Q(project__project_incharge=request.user)
        | Q(project__isnull=True)
    )
    
    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        if not (
            request.user.is_admin
            or project.managers.filter(pk=request.user.pk).exists()
            or project.members.filter(pk=request.user.pk).exists()
            or project.project_incharge_id == request.user.pk
        ):
            return JsonResponse([], safe=False)
        categories = FileCategory.objects.filter(project_id=project_id, is_in_trash=False)
    else:
        # Load directory list from authorized projects
        categories = FileCategory.objects.filter(is_in_trash=False)
        if not request.user.is_admin:
            categories = categories.filter(q_filter)
    
    data = []
    for cat in categories.select_related('project'):
        data.append({
            "id": cat.id,
            "name": cat.full_path,
            "project_name": cat.project.name if cat.project else "Global"
        })
    
    return JsonResponse(data, safe=False)


@login_required
def category_create(request, pk):
    """
    Initializes new directory folder nodes under projects.
    Enforces project-wide membership validation and logs actions to Audit logs.
    """
    project = get_object_or_404(Project, pk=pk)
    parent_id = request.GET.get("parent_id")
    parent = get_object_or_404(FileCategory, pk=parent_id) if parent_id else None
    
    if not (
        project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
    ):
        messages.error(request, "No access to create folders.")
        return redirect("files:project_files", pk=project.pk)
    
    form = FileCategoryForm(request.POST or None, initial={"project": project, "parent": parent})
    if request.method == "POST" and form.is_valid():
        cat = form.save(commit=False)
        cat.created_by = request.user
        if parent:
            cat.parent = parent
        cat.save()
        
        # Log creation
        AuditLog.objects.create(
            user=request.user,
            action_type="create",
            module="folder",
            entity_id=str(cat.pk),
            entity_name=cat.name,
            details=f"Project: {project.name} | Folder '{cat.name}' created." + (f" (Parent: {parent.name})" if parent else "")
        )
        
        messages.success(request, f'Folder "{cat.name}" created successfully.')
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("files:project_files", pk=project.pk)
    
    return render(
        request, "files/category_form.html", {
            "form": form, 
            "project": project,
            "parent": parent
        }
    )


@login_required
def category_edit(request, pk):
    """
    Edits folder details. Restricted to project members, PMs, and Admins.
    Note: Renaming a folder triggers cascade changes in subdirectories and file paths.
    """
    cat = get_object_or_404(FileCategory, pk=pk)
    project = cat.project
    
    # Permission verification
    if not (request.user.is_admin or 
            getattr(request.user, 'is_project_manager', False) or
            (project and (project.managers.filter(pk=request.user.pk).exists() or 
                          project.members.filter(pk=request.user.pk).exists())) or
            cat.created_by == request.user):
        messages.error(request, "No permission to edit this folder.")
        return redirect("files:project_files", pk=project.pk if project else 0)
    
    form = FileCategoryForm(request.POST or None, instance=cat)
    if request.method == "POST" and form.is_valid():
        form.save()
        
        # Log edit
        AuditLog.objects.create(
            user=request.user,
            action_type="edit",
            module="folder",
            entity_id=str(cat.pk),
            entity_name=cat.name,
            details=f"Project: {project.name if project else 'N/A'} | Folder '{cat.name}' updated."
        )
        
        messages.success(request, f'Folder "{cat.name}" updated.')
        if project:
            return redirect("files:project_files", pk=project.pk)
        return redirect("files:file_list")
        
    return render(request, "files/category_form.html", {
        "form": form, 
        "project": project,
        "is_edit": True,
        "category": cat
    })
