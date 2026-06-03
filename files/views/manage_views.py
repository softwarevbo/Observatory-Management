from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import ProjectFile, FileCategory
from tasks.models import Project, AuditLog

@login_required
def category_delete(request, pk):
    cat = get_object_or_404(FileCategory, pk=pk)
    project = cat.project
    # Check permissions
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
        cat.is_in_trash = True
        cat.deleted_at = timezone.now()
        cat.deleted_by = request.user
        cat.save()
        
        # Recursively trash subcategories and their files
        def trash_category_tree(category, user):
            now = timezone.now()
            # Trash files in this category
            ProjectFile.objects.filter(category=category, is_in_trash=False).update(
                is_in_trash=True, deleted_at=now, deleted_by=user
            )
            # Recursively trash children
            for child in category.children.filter(is_in_trash=False):
                child.is_in_trash = True
                child.deleted_at = now
                child.deleted_by = user
                child.save()
                trash_category_tree(child, user)
                
        trash_category_tree(cat, request.user)
        
        AuditLog.objects.create(
            user=request.user,
            action_type="delete",
            module="folder",
            entity_id=str(cat.pk),
            entity_name=cat.name,
            details=f"Project: {project.name} | Folder '{cat.name}' moved to trash."
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
    Dedicated page to move a file or a folder to another folder (category).
    Supports GET (show move page) and POST (perform move).
    Query parameters for GET: type ('file' or 'folder'), id (item_id).
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

    # Permission check (can edit/move)
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
            # Prevent moving a folder into itself or its descendants
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

    # GET request - show move page
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
    Portal page for a resource (file or folder) or an entire project to choose management actions.
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
    
    # Permission check for individual item
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
    Shows movement and deletion logs of files and folders for project managers.
    """
    if not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "Access restricted to project managers.")
        return redirect("files:file_list")
        
    logs = AuditLog.objects.filter(module__in=["file", "folder"]).order_by("-timestamp")
    
    return render(request, "files/file_audit_logs.html", {"logs": logs})
