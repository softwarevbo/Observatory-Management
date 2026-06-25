from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from tasks.models import Project, Task, Requirement, AuditLog
from ..models import ProjectFile, FileCategory, SystemSettings
from ..forms import FileUploadForm

"""
This module processes single/multiple file uploads and dynamic directory reconstruction.
"""

@login_required
def file_upload(request):
    """
    Handles file upload requests (both traditional form posts and asynchronous batch operations).
    Recreates directories dynamically from relative paths during drag-and-drop actions.
    Checks file sizes against global settings constraints.
    """
    project_id = request.POST.get("project") or request.GET.get("project")
    task_id = request.POST.get("task") or request.GET.get("task")
    requirement_id = request.POST.get("requirement") or request.GET.get("requirement")
    parent_id = request.GET.get("parent_id")
    project = Project.objects.filter(pk=project_id).first() if project_id else None
    task = Task.objects.filter(pk=task_id).first() if task_id else None
    requirement = Requirement.objects.filter(pk=requirement_id).first() if requirement_id else None
    
    max_size_bytes = SystemSettings.get_max_size_bytes()
    
    # Establish project context from nested elements
    if not project and task:
        project = task.project
    if not project and requirement:
        project = requirement.project
    parent = ProjectFile.objects.filter(pk=parent_id).first() if parent_id else None
    
    # Access authorization check
    if project and not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "You do not have access to upload files to this project.")
        return redirect("tasks:project_list")
    
    # Pre-populate properties on new revisions
    initial = {"parent_file": parent}
    if parent:
        project = parent.project
        task = parent.task
        initial.update({
            "project": parent.project,
            "task": parent.task,
            "category": parent.category,
            "title": parent.title,
            "description": parent.description,
            "is_public": parent.is_public,
        })

    form = FileUploadForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
        project=project,
        task=task,
        initial=initial,
    )

    if request.method == "POST":
        uploaded_files, relative_paths = request.FILES.getlist(
            "files"
        ), request.POST.getlist("relative_paths")
        
        # Batch upload handling
        if uploaded_files:
            uploaded, description, is_public, base_cat = (
                [],
                request.POST.get("description", ""),
                request.POST.get("is_public") == "on",
                (
                    FileCategory.objects.filter(pk=request.POST.get("category")).first()
                    if request.POST.get("category")
                    else None
                ),
            )
            category_cache = {}
            for idx, f in enumerate(uploaded_files):
                # Validate size limits
                if f.size > max_size_bytes:
                    messages.error(request, f"File {f.name} exceeds the maximum allowed size.")
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"success": False, "error": f"File {f.name} exceeds the maximum allowed size."})
                    continue

                rel_path = relative_paths[idx] if idx < len(relative_paths) else f.name
                file_cat = base_cat
                
                # Reconstruct folder trees dynamically to match drag-and-drop layouts
                if project and "/" in rel_path:
                    current_parent = base_cat
                    for part in rel_path.split("/")[:-1]:
                        cache_key = (current_parent.pk if current_parent else None, part)
                        if cache_key in category_cache:
                            current_parent = category_cache[cache_key]
                        else:
                            cat_obj = FileCategory.objects.filter(
                                name=part,
                                project=project,
                                parent=current_parent,
                                is_in_trash=False
                            ).first()
                            if not cat_obj:
                                cat_obj = FileCategory.objects.create(
                                    name=part,
                                    project=project,
                                    parent=current_parent,
                                    created_by=request.user
                                )
                            category_cache[cache_key] = cat_obj
                            current_parent = cat_obj
                    file_cat = current_parent
                    
                # Version control matching logic
                existing = (
                    ProjectFile.objects.filter(
                        original_name=f.name,
                        project=project,
                        category=file_cat,
                        task=task,
                    )
                    .order_by("-version")
                    .first()
                )
                parent_file = parent or existing
                version = (parent_file.version + 1) if parent_file else 1
                
                pf = ProjectFile.objects.create(
                    file=f,
                    original_name=f.name,
                    project=project,
                    category=file_cat,
                    task=task,
                    uploaded_by=request.user,
                    last_modified_by=request.user,
                    description=description,
                    is_public=is_public,
                    version=version,
                    parent_file=parent_file,
                )
                
                # Write action log entries
                AuditLog.objects.create(
                    user=request.user,
                    action_type="create",
                    module="file",
                    entity_id=str(pf.pk),
                    entity_name=pf.display_name,
                    details=f"Project: {project.name if project else 'N/A'} | File '{pf.display_name}' uploaded (v{version})."
                )
                uploaded.append(
                    {
                        "id": pf.pk,
                        "name": pf.display_name,
                        "size": pf.file_size_display,
                        "type": pf.file_type,
                        "icon": pf.icon_class,
                        "url": f"/files/{pf.pk}/",
                    }
                )
                
            # JSON response block for asynchronous API calls
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                messages.success(request, f"{len(uploaded)} file(s) uploaded successfully.")
                redirect_url = ""
                if len(uploaded) == 1:
                    redirect_url = uploaded[0]["url"]
                elif project:
                    from django.urls import reverse
                    redirect_url = reverse("files:project_files", kwargs={"pk": project.pk})
                else:
                    from django.urls import reverse
                    redirect_url = reverse("files:file_list")
                return JsonResponse({"success": True, "files": uploaded, "redirect_url": redirect_url})
                
            messages.success(request, f"{len(uploaded)} file(s) uploaded successfully.")
            return (
                redirect("files:project_files", pk=project.pk)
                if project
                else redirect("files:file_list")
            )
            
        # Standard form upload handling
        if "file" in request.FILES and form.is_valid():
            pf = form.save(commit=False)
            pf.uploaded_by, pf.original_name = request.user, request.FILES["file"].name
            if not pf.parent_file:
                existing = (
                    ProjectFile.objects.filter(
                        original_name=pf.original_name,
                        project=pf.project,
                        category=pf.category,
                        task=pf.task,
                    )
                    .order_by("-version")
                    .first()
                )
                if existing:
                    pf.parent_file = existing
            if pf.parent_file:
                pf.version = pf.parent_file.version + 1
            pf.save()
            
            # Log standard upload
            AuditLog.objects.create(
                user=request.user,
                action_type="create",
                module="file",
                entity_id=str(pf.pk),
                entity_name=pf.display_name,
                details=f"Project: {pf.project.name if pf.project else 'N/A'} | File '{pf.display_name}' uploaded (v{pf.version})."
            )
            
            messages.success(request, f'"{pf.display_name}" uploaded successfully.')
            return redirect("files:file_detail", pk=pf.pk)
            
        messages.error(
            request,
            (
                "Please fix the errors below."
                if "file" in request.FILES
                else "Please select at least one file to upload."
            ),
        )
        
    return render(
        request,
        "files/file_upload.html",
        {
            "form": form,
            "project": project,
            "task": task,
            "max_size_bytes": max_size_bytes,
            "max_size_gb": max_size_bytes / (1024 * 1024 * 1024),
        },
    )
