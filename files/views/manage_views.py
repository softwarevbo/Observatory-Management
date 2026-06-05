from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import ProjectFile, FileCategory
from tasks.models import Project, AuditLog

"""
This module processes folder node deletions, bulk file operations, movements,
and folder resource comments.
"""

def _collect_all_descendant_ids(root_category_id):
    """
    Iteratively collects all FileCategory IDs that are descendants of a folder.
    Uses iterative database query lookups over parent IDs instead of loading large model instances,
    optimizing performance for deep folder hierarchies.
    Returns a list of category PKs (integers).
    """
    all_ids = [root_category_id]
    queue = [root_category_id]
    while queue:
        children_ids = list(
            FileCategory.objects.filter(parent_id__in=queue, is_in_trash=False)
            .values_list('pk', flat=True)
        )
        all_ids.extend(children_ids)
        queue = children_ids
    return all_ids


def _bulk_trash_category_tree(category_id, user):
    """
    Trashes an entire folder tree (nested subfolders and files) using bulk database updates,
    minimizing query count.
    Returns a tuple: (file_count, folder_count).
    """
    now = timezone.now()

    # 1. Collect all descendant category PKs
    all_cat_ids = _collect_all_descendant_ids(category_id)

    # 2. Bulk update all files in any of these categories
    files_updated = ProjectFile.objects.filter(
        category_id__in=all_cat_ids, is_in_trash=False
    ).update(is_in_trash=True, deleted_at=now, deleted_by=user)

    # 3. Bulk update all subdirectories (excluding the root category itself)
    child_ids = [pk for pk in all_cat_ids if pk != category_id]
    if child_ids:
        FileCategory.objects.filter(pk__in=child_ids).update(
            is_in_trash=True, deleted_at=now, deleted_by=user
        )

    return files_updated, len(child_ids)


@login_required
def category_delete(request, pk):
    """
    Handles folder deletions. Bulk-trashes subdirectories and nested files,
    soft-trashes the root folder itself, and writes action logs to system audit logs.
    """
    cat = get_object_or_404(FileCategory, pk=pk)
    project = cat.project
    
    # Permission verification
    if not (request.user.is_admin or 
            getattr(request.user, 'is_project_manager', False) or
            (project and (project.managers.filter(pk=request.user.pk).exists() or 
                          project.members.filter(pk=request.user.pk).exists())) or
            cat.created_by == request.user):
        messages.error(request, "No permission to delete this folder.")
        if project:
            return redirect("files:project_files", pk=project.pk)
        return redirect("files:file_list")
    
    if request.method == "POST":
        name = cat.name
        now = timezone.now()

        # Bulk-trash nested contents recursively
        _bulk_trash_category_tree(cat.pk, request.user)

        # Soft-trash the root folder category itself
        cat.is_in_trash = True
        cat.deleted_at = now
        cat.deleted_by = request.user
        cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])

        # Write audit logs
        AuditLog.objects.create(
            user=request.user,
            action_type="delete",
            module="folder",
            entity_id=str(cat.pk),
            entity_name=name,
            details=f"Project: {project.name} | Folder '{name}' and all contents moved to trash."
        )

        messages.success(request, f'Folder "{name}" and its contents moved to trash.')
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("files:project_files", pk=project.pk)

    return render(request, "files/category_confirm_delete.html", {"category": cat})


@login_required
def move_item(request):
    """
    Handles moving a file or folder to another destination folder.
    Prevents circular references (e.g. moving a folder inside itself or its own subdirectories).
    """
    item_type = request.POST.get("item_type") or request.GET.get("type")
    item_id = request.POST.get("item_id") or request.GET.get("id")
    
    if not item_type or not item_id:
        messages.error(request, "Missing item information for movement.")
        return redirect("files:file_list")

    item = None
    project = None
    if item_type == "file":
        item = get_object_or_404(ProjectFile, pk=item_id)
        project = item.project
    elif item_type == "folder":
        item = get_object_or_404(FileCategory, pk=item_id)
        project = item.project
    else:
        messages.error(request, "Invalid item type.")
        return redirect("files:file_list")

    # Permission verification
    can_move = False
    if request.user.is_admin or getattr(request.user, 'is_project_manager', False):
        can_move = True
    elif project and (project.managers.filter(pk=request.user.pk).exists() or project.members.filter(pk=request.user.pk).exists()):
        can_move = True
    elif item_type == "file" and item.uploaded_by == request.user:
        can_move = True
    elif item_type == "folder" and item.created_by == request.user:
        can_move = True

    if not can_move:
        messages.error(request, "No permission to move this item.")
        return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))

    if request.method == "POST":
        target_cat_id = request.POST.get("target_category_id")
        target_cat = None
        if target_cat_id:
            target_cat = get_object_or_404(FileCategory, pk=target_cat_id)
            
        if item_type == "file":
            item.category = target_cat
            item.save()
            
            # Log movement
            AuditLog.objects.create(
                user=request.user,
                action_type="move",
                module="file",
                entity_id=str(item.pk),
                entity_name=item.display_name,
                details=f"Project: {project.name if project else 'Personal'} | Moved to '{target_cat.name if target_cat else 'Root'}'"
            )
            messages.success(request, f'File "{item.display_name}" moved successfully.')
        elif item_type == "folder":
            # Circular inheritance check: verify target folder is not a child of the folder being moved
            if target_cat:
                temp = target_cat
                while temp:
                    if temp.pk == item.pk:
                        messages.error(request, "Cannot move a folder into itself or its subfolders.")
                        return render(request, "files/move_item.html", {
                            "item": item,
                            "item_type": item_type,
                            "project": project,
                            "categories": FileCategory.objects.filter(project=project) if project else FileCategory.objects.filter(project__isnull=True)
                        })
                    temp = temp.parent
            
            item.parent = target_cat
            item.save()
            
            # Log movement
            AuditLog.objects.create(
                user=request.user,
                action_type="move",
                module="folder",
                entity_id=str(item.pk),
                entity_name=item.name,
                details=f"Project: {project.name if project else 'Personal'} | Moved to '{target_cat.name if target_cat else 'Root'}'"
            )
            messages.success(request, f'Folder "{item.name}" moved successfully.')
            
        if project:
            return redirect("files:project_files", pk=project.pk)
        return redirect("files:file_list")

    # Render move selection template
    categories = []
    if project:
        categories = FileCategory.objects.filter(project=project).order_by('name')
    else:
        categories = FileCategory.objects.filter(project__isnull=True).order_by('name')

    return render(request, "files/move_item.html", {
        "item": item,
        "item_type": item_type,
        "project": project,
        "categories": categories,
    })


@login_required
def manage_resource(request):
    """
    Renders folder discussion portals or project file management views.
    Includes comment form validation.
    """
    item_type = request.GET.get("type")
    item_id = request.GET.get("id")
    project_id = request.GET.get("project_id")
    
    project = None
    item = None
    
    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        messages.error(request, "This portal has been disabled.")
        return redirect("tasks:project_detail", pk=project.pk)

    if not item_type or not item_id:
        messages.error(request, "Missing information.")
        return redirect("files:file_list")

    if item_type == "file":
        item = get_object_or_404(ProjectFile, pk=item_id)
        project = item.project
    elif item_type == "folder":
        item = get_object_or_404(FileCategory, pk=item_id)
        project = item.project
    
    # Permission verification
    can_manage = False
    if request.user.is_admin or request.user.is_project_manager:
        can_manage = True
    elif project and (project.managers.filter(pk=request.user.pk).exists() or project.members.filter(pk=request.user.pk).exists()):
        can_manage = True
    elif item_type == "file" and item.uploaded_by == request.user:
        can_manage = True
    elif item_type == "folder" and item.created_by == request.user:
        can_manage = True
        
    if not can_manage:
        messages.error(request, "No permission to manage this resource.")
        return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))

    comment_form = None
    comments = []
    if item_type == "folder":
        from ..forms import FileCommentForm
        comment_form = FileCommentForm(request.POST or None)
        if request.method == "POST" and comment_form.is_valid():
            c = comment_form.save(commit=False)
            c.category = item
            c.author = request.user
            c.save()
            messages.success(request, "Comment added.")
            return redirect(request.get_full_path())
        comments = item.comments.select_related("author").all()

    return render(request, "files/manage_resource.html", {
        "item": item,
        "item_type": item_type,
        "project": project,
        "is_project_portal": False,
        "comment_form": comment_form,
        "comments": comments,
    })


@login_required
def file_audit_logs(request):
    """
    Renders system Audit Logs specifically tracking file and folder updates, moves, and deletions.
    Restricted to Admins and PMs.
    """
    if not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "Access restricted to project managers.")
        return redirect("files:file_list")
        
    logs = AuditLog.objects.filter(module__in=["file", "folder"]).order_by("-timestamp")
    
    return render(request, "files/file_audit_logs.html", {"logs": logs})


@login_required
def bulk_file_action(request):
    """
    Handles bulk updates (moves and soft-deletions) on selected files and folders.
    Optimizes database performance by trashing files in a single UPDATE query,
    and performing bulk_create for audits logs.
    """
    if request.method == "POST":
        action = request.POST.get("action")
        file_ids = request.POST.getlist("selected_files")
        folder_ids = request.POST.getlist("selected_folders")
        
        if not file_ids and not folder_ids:
            messages.error(request, "No files or folders selected.")
            return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))
            
        allowed_files = []
        if file_ids:
            files = ProjectFile.objects.filter(pk__in=file_ids, is_in_trash=False)
            for pf in files:
                project = pf.project
                can_manage = False
                if request.user.is_admin or getattr(request.user, 'is_project_manager', False):
                    can_manage = True
                elif project and (project.managers.filter(pk=request.user.pk).exists() or project.members.filter(pk=request.user.pk).exists()):
                    can_manage = True
                elif pf.uploaded_by == request.user:
                    can_manage = True
                
                if can_manage:
                    allowed_files.append(pf)

        allowed_folders = []
        if folder_ids:
            folders = FileCategory.objects.filter(pk__in=folder_ids, is_in_trash=False)
            for cat in folders:
                project = cat.project
                can_manage = False
                if request.user.is_admin or getattr(request.user, 'is_project_manager', False):
                    can_manage = True
                elif project and (project.managers.filter(pk=request.user.pk).exists() or project.members.filter(pk=request.user.pk).exists()):
                    can_manage = True
                elif cat.created_by == request.user:
                    can_manage = True
                
                if can_manage:
                    allowed_folders.append(cat)

        if not allowed_files and not allowed_folders:
            messages.error(request, "You do not have permission to manage the selected items.")
            return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))
            
        if action == "delete":
            now = timezone.now()

            # Bulk trash selected files using a single UPDATE query
            if allowed_files:
                file_ids = [pf.pk for pf in allowed_files]
                ProjectFile.objects.filter(pk__in=file_ids).update(
                    is_in_trash=True, deleted_at=now, deleted_by=request.user
                )
                # Bulk create audit logs
                AuditLog.objects.bulk_create([
                    AuditLog(
                        user=request.user,
                        action_type="delete",
                        module="file",
                        entity_id=str(pf.pk),
                        entity_name=pf.display_name,
                        details=f"Project: {pf.project.name if pf.project else 'Personal'} | File '{pf.display_name}' moved to trash via bulk action."
                    )
                    for pf in allowed_files
                ])

            # Bulk trash selected folder subtrees (O(depth) queries per folder)
            if allowed_folders:
                folder_audit_entries = []
                for cat in allowed_folders:
                    # Trashes subfolders and nested files recursively
                    _bulk_trash_category_tree(cat.pk, request.user)
                    
                    # Trash root category node itself
                    cat.is_in_trash = True
                    cat.deleted_at = now
                    cat.deleted_by = request.user
                    cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
                    folder_audit_entries.append(AuditLog(
                        user=request.user,
                        action_type="delete",
                        module="folder",
                        entity_id=str(cat.pk),
                        entity_name=cat.name,
                        details=f"Project: {cat.project.name if cat.project else 'Personal'} | Folder '{cat.name}' moved to trash via bulk action."
                    ))
                AuditLog.objects.bulk_create(folder_audit_entries)

            messages.success(request, "Successfully moved selected file(s) / folder(s) to trash.")
            
        elif action == "move":
            target_cat_id = request.POST.get("target_category_id")
            target_cat = None
            if target_cat_id:
                target_cat = get_object_or_404(FileCategory, pk=target_cat_id)
            
            # Bulk move files
            if allowed_files:
                for pf in allowed_files:
                    pf.category = target_cat
                    if target_cat:
                        pf.project = target_cat.project
                    pf.save()
                    
                    # Log movement
                    AuditLog.objects.create(
                        user=request.user,
                        action_type="move",
                        module="file",
                        entity_id=str(pf.pk),
                        entity_name=pf.display_name,
                        details=f"Project: {pf.project.name if pf.project else 'Personal'} | Moved to '{target_cat.name if target_cat else 'Root'}' via bulk action."
                    )
            
            # Bulk move folders
            if allowed_folders:
                moved_count = 0
                for cat in allowed_folders:
                    # Circular hierarchy check: verify target folder is not a child of the folder being moved
                    if target_cat:
                        temp = target_cat
                        is_self_or_descendant = False
                        while temp:
                            if temp.pk == cat.pk:
                                is_self_or_descendant = True
                                break
                            temp = temp.parent
                        if is_self_or_descendant:
                            continue
                    
                    cat.parent = target_cat
                    if target_cat:
                        cat.project = target_cat.project
                    cat.save()
                    moved_count += 1
                    
                    # Log movement
                    AuditLog.objects.create(
                        user=request.user,
                        action_type="move",
                        module="folder",
                        entity_id=str(cat.pk),
                        entity_name=cat.name,
                        details=f"Project: {cat.project.name if cat.project else 'Personal'} | Moved Folder to parent '{target_cat.name if target_cat else 'Root'}' via bulk action."
                    )
            messages.success(request, f"Successfully moved selected file(s) / folder(s) to target folder.")
            
    return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))
