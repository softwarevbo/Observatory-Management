import os

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from ..models import Project, Task, Requirement
from bugs.models import BugReport
from testcases.models import TestCase
from notes.models import KnowledgeBaseNote
from files.models import ProjectFile, FileCategory


def _restore_category_ancestors(category, user=None):
    """Restore parent folders needed to make a restored item visible."""
    from files.views.manage_views import _bulk_trash_category_tree
    parent = category.parent
    any_overridden = False
    while parent:
        if parent.is_in_trash:
            active_cat = FileCategory.objects.filter(
                name=parent.name,
                parent=parent.parent,
                project=parent.project,
                is_in_trash=False
            ).first()
            if active_cat:
                _bulk_trash_category_tree(active_cat.pk, user or parent.deleted_by)
                active_cat.is_in_trash = True
                active_cat.deleted_at = timezone.now()
                active_cat.deleted_by = user or parent.deleted_by
                active_cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
                any_overridden = True

            parent.is_in_trash = False
            parent.deleted_at = None
            parent.deleted_by = None
            parent.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
        parent = parent.parent
    return any_overridden


def _restore_category_subtree(category):
    """Restore a selected folder and only its own deleted contents."""
    if category.is_in_trash:
        category.is_in_trash = False
        category.deleted_at = None
        category.deleted_by = None
        category.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])

    category.files.filter(is_in_trash=True).update(
        is_in_trash=False,
        hidden_from_user_trash=False,
        deleted_at=None,
        deleted_by=None,
    )

    for child in category.children.filter(is_in_trash=True):
        _restore_category_subtree(child)


def _restore_file_with_ancestors(file_obj, user=None):
    """Restore parent folders needed to make a restored file visible."""
    from files.views.manage_views import _bulk_trash_category_tree
    category = file_obj.category
    any_overridden = False
    while category:
        if category.is_in_trash:
            active_cat = FileCategory.objects.filter(
                name=category.name,
                parent=category.parent,
                project=category.project,
                is_in_trash=False
            ).first()
            if active_cat:
                _bulk_trash_category_tree(active_cat.pk, user or category.deleted_by)
                active_cat.is_in_trash = True
                active_cat.deleted_at = timezone.now()
                active_cat.deleted_by = user or category.deleted_by
                active_cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
                any_overridden = True

            category.is_in_trash = False
            category.deleted_at = None
            category.deleted_by = None
            category.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
        category = category.parent

    file_obj.is_in_trash = False
    file_obj.hidden_from_user_trash = False
    file_obj.deleted_at = None
    file_obj.deleted_by = None
    file_obj.save(update_fields=["is_in_trash", "hidden_from_user_trash", "deleted_at", "deleted_by", "updated_at"])
    return any_overridden


@login_required
def global_search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return render(
            request, "search/search_results.html", {"query": query, "results": {}}
        )

    tasks = Task.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query)
    ).distinct()
    projects = Project.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
    ).distinct()
    files = ProjectFile.objects.filter(
        Q(original_name__icontains=query) | Q(description__icontains=query)
    ).distinct()

    if not (request.user.is_admin or request.user.is_project_manager):
        tasks = tasks.filter(
            Q(assignees=request.user) | Q(project__managers=request.user)
        ).distinct()
        projects = projects.filter(
            Q(members=request.user) | Q(managers=request.user)
        ).distinct()
        files = files.filter(
            Q(project__members=request.user) | Q(project__managers=request.user)
        ).distinct()

    results = {"tasks": tasks[:20], "projects": projects[:20], "files": files[:20]}
    return render(
        request, "search/search_results.html", {"query": query, "results": results}
    )  # Updated path

@login_required
def trash_view(request):
    user = request.user
    search_query = request.GET.get("q", "")
    project_id = request.GET.get("project", "")
    deleted_by_id = request.GET.get("deleted_by", "")
    days_val = request.GET.get("days", "")
    trash_cat_id = request.GET.get("trash_cat_id", "")
    
    current_cat = None
    breadcrumbs = []
    if trash_cat_id:
        current_cat = get_object_or_404(FileCategory, pk=trash_cat_id)
        # build breadcrumbs (only categories in trash)
        temp = current_cat
        while temp:
            breadcrumbs.append(temp)
            temp = temp.parent
        breadcrumbs.reverse()
    
    def filter_qs(qs):
        if project_id:
            qs = qs.filter(project_id=project_id)
        if deleted_by_id:
            qs = qs.filter(deleted_by_id=deleted_by_id)
        if days_val:
            from datetime import timedelta
            from django.utils import timezone
            try:
                cutoff = timezone.now() - timedelta(days=int(days_val))
                qs = qs.filter(deleted_at__gte=cutoff)
            except (ValueError, TypeError):
                pass
        if search_query:
            if hasattr(qs.model, 'title'):
                qs = qs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
            elif hasattr(qs.model, 'name'):
                qs = qs.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
            elif hasattr(qs.model, 'original_name'):
                qs = qs.filter(Q(original_name__icontains=search_query) | Q(description__icontains=search_query))
        return qs.distinct()

    if user.is_admin or user.is_project_manager:
        tasks = filter_qs(Task.objects.filter(is_in_trash=True))
        requirements = filter_qs(Requirement.objects.filter(is_in_trash=True))
        notes = filter_qs(KnowledgeBaseNote.objects.filter(is_in_trash=True))
        test_cases = filter_qs(TestCase.objects.filter(is_in_trash=True))
        bugs = filter_qs(BugReport.objects.filter(is_in_trash=True))
        projects = Project.objects.all()
        
        if current_cat:
            categories = filter_qs(FileCategory.objects.filter(parent=current_cat, is_in_trash=True))
            files = filter_qs(ProjectFile.objects.filter(category=current_cat, is_in_trash=True))
        else:
            categories = filter_qs(FileCategory.objects.filter(is_in_trash=True).filter(
                Q(parent__isnull=True) | Q(parent__is_in_trash=False)
            ))
            files = filter_qs(ProjectFile.objects.filter(is_in_trash=True).filter(
                Q(category__isnull=True) | Q(category__is_in_trash=False)
            ))
        
        # Get list of all users who have items in trash for the filter dropdown
        from django.contrib.auth import get_user_model
        User = get_user_model()
        deleters = User.objects.filter(
            Q(deleted_tasks__isnull=False) |
            Q(deleted_requirements__isnull=False) |
            Q(deleted_files__isnull=False) |
            Q(deleted_notes__isnull=False) |
            Q(deleted_test_cases__isnull=False) |
            Q(deleted_bugs__isnull=False) |
            Q(deleted_categories__isnull=False)
        ).distinct()
    else:
        # Everyone else sees ONLY items they personally deleted
        tasks = filter_qs(Task.objects.filter(deleted_by=user, is_in_trash=True))
        requirements = filter_qs(Requirement.objects.filter(deleted_by=user, is_in_trash=True))
        notes = filter_qs(KnowledgeBaseNote.objects.filter(deleted_by=user, is_in_trash=True))
        test_cases = filter_qs(TestCase.objects.filter(deleted_by=user, is_in_trash=True))
        bugs = filter_qs(BugReport.objects.filter(deleted_by=user, is_in_trash=True))
        deleters = []
        
        if current_cat:
            categories = filter_qs(FileCategory.objects.filter(parent=current_cat, deleted_by=user, is_in_trash=True))
            files = filter_qs(ProjectFile.objects.filter(category=current_cat, deleted_by=user, is_in_trash=True))
        else:
            categories = filter_qs(FileCategory.objects.filter(deleted_by=user, is_in_trash=True).filter(
                Q(parent__isnull=True) | Q(parent__is_in_trash=False)
            ))
            files = filter_qs(ProjectFile.objects.filter(deleted_by=user, is_in_trash=True).filter(
                Q(category__isnull=True) | Q(category__is_in_trash=False)
            ))
        
        # Projects list for filter dropdown should still be restricted to involved projects
        projects = Project.objects.filter(
            Q(managers=user) | Q(members=user) | Q(project_incharge=user)
        ).distinct()

    return render(request, "tasks/trash.html", {
        "tasks": tasks.order_by("project__name"),
        "requirements": requirements.order_by("project__name"),
        "files": files.order_by("project__name"),
        "notes": notes.order_by("project__name"),
        "test_cases": test_cases.order_by("project__name"),
        "bugs": bugs.order_by("project__name"),
        "categories": categories.order_by("project__name"),
        "projects": projects,
        "deleters": deleters,
        "search_query": search_query,
        "project_filter": project_id,
        "deleted_by_filter": deleted_by_id,
        "days_filter": request.GET.get("days", ""),
        "current_cat": current_cat,
        "breadcrumbs": breadcrumbs,
    })


@login_required
@login_required
def task_restore(request, pk):
    task = get_object_or_404(Task, pk=pk)
    # Restore allowed for Admin, PM, Incharge, or Creator
    is_authorized = (request.user.is_admin or 
                     task.project.is_manager(request.user) or 
                     task.project.is_incharge(request.user) or 
                     task.created_by == request.user)
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this task.")
        return redirect("tasks:trash")
        
    task.is_in_trash = False
    task.deleted_at = None
    task.deleted_by = None
    task.save()
    messages.success(request, f"Task '{task.title}' restored.")
    return redirect("tasks:trash")


@login_required
def task_permanent_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or task.project.is_manager(request.user)):
        messages.error(request, "Only managers can permanently delete tasks.")
        return redirect("tasks:trash")
        
    task.delete()
    messages.success(request, "Task permanently deleted from database.")
    return redirect("tasks:trash")


@login_required
def requirement_restore(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    # Restore allowed for Admin, PM, Incharge, or Creator
    is_authorized = (request.user.is_admin or 
                     req.project.is_manager(request.user) or 
                     req.project.is_incharge(request.user) or 
                     req.created_by == request.user)
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this requirement.")
        return redirect("tasks:trash")
        
    req.is_in_trash = False
    req.deleted_at = None
    req.deleted_by = None
    req.save()
    messages.success(request, f"Requirement '{req.name}' restored.")
    return redirect("tasks:trash")


@login_required
def requirement_permanent_delete(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or req.project.is_manager(request.user)):
        messages.error(request, "Only managers can permanently delete requirements.")
        return redirect("tasks:trash")
        
    req.delete()
    messages.success(request, "Requirement permanently deleted from database.")
    return redirect("tasks:trash")


from notes.views import note_restore, note_permanent_delete


@login_required
def testcase_restore(request, pk):
    tc = get_object_or_404(TestCase, pk=pk)
    # Restore allowed for Admin, PM, Incharge, or Creator
    is_authorized = (request.user.is_admin or 
                     tc.project.is_manager(request.user) or 
                     tc.project.is_incharge(request.user) or 
                     tc.created_by == request.user)
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this test case.")
        return redirect("tasks:trash")
        
    tc.is_in_trash = False
    tc.deleted_at = None
    tc.deleted_by = None
    tc.save()
    messages.success(request, f"Test Case '{tc.title}' restored.")
    return redirect("tasks:trash")


@login_required
def testcase_permanent_delete(request, pk):
    tc = get_object_or_404(TestCase, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or tc.project.is_manager(request.user)):
        messages.error(request, "Only managers can permanently delete test cases.")
        return redirect("tasks:trash")
        
    tc.delete()
    messages.success(request, "Test Case permanently deleted from database.")
    return redirect("tasks:trash")


@login_required
def category_restore(request, pk):
    cat = get_object_or_404(FileCategory, pk=pk)
    # Restore allowed for Admin, PM, Incharge, Creator, or Project Member
    is_authorized = (
        request.user.is_admin or 
        cat.project.is_manager(request.user) or 
        cat.project.is_incharge(request.user) or 
        cat.created_by == request.user or
        cat.project.members.filter(pk=request.user.pk).exists()
    )
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this folder.")
        return redirect("tasks:trash")

    overridden = False
    from files.views.manage_views import _bulk_trash_category_tree
    with transaction.atomic():
        # Check if an active category with the same name, parent, and project already exists
        active_cat = FileCategory.objects.filter(
            name=cat.name,
            parent=cat.parent,
            project=cat.project,
            is_in_trash=False
        ).first()
        
        if active_cat:
            # Move the existing active folder to trash (override)
            _bulk_trash_category_tree(active_cat.pk, request.user)
            active_cat.is_in_trash = True
            active_cat.deleted_at = timezone.now()
            active_cat.deleted_by = request.user
            active_cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
            overridden = True

        if _restore_category_ancestors(cat, request.user):
            overridden = True
        _restore_category_subtree(cat)

    if overridden:
        messages.success(
            request, 
            f"Folder '{cat.name}' restored. The existing folder with the same name in the repository was overridden."
        )
    else:
        messages.success(request, f"Folder '{cat.name}' restored with its original path.")
        
    trash_cat_id = request.GET.get("trash_cat_id") or request.POST.get("trash_cat_id")
    if trash_cat_id:
        return redirect(f"{reverse('tasks:trash')}?trash_cat_id={trash_cat_id}")
    return redirect("tasks:trash")


@login_required
def trash_bulk_restore(request):
    if request.method != "POST":
        return redirect("tasks:trash")

    category_ids = request.POST.getlist("categories")
    file_ids = request.POST.getlist("files")
    trash_cat_id = request.GET.get("trash_cat_id") or request.POST.get("trash_cat_id")
    restored_count = 0
    overridden_count = 0
    from files.views.manage_views import _bulk_trash_category_tree

    for cat in FileCategory.objects.filter(pk__in=category_ids, is_in_trash=True).select_related("project", "created_by"):
        is_authorized = (
            request.user.is_admin
            or cat.project.is_manager(request.user)
            or cat.project.is_incharge(request.user)
            or cat.created_by == request.user
            or cat.project.members.filter(pk=request.user.pk).exists()
        )
        if is_authorized:
            with transaction.atomic():
                has_override = False
                active_cat = FileCategory.objects.filter(
                    name=cat.name,
                    parent=cat.parent,
                    project=cat.project,
                    is_in_trash=False
                ).first()
                if active_cat:
                    _bulk_trash_category_tree(active_cat.pk, request.user)
                    active_cat.is_in_trash = True
                    active_cat.deleted_at = timezone.now()
                    active_cat.deleted_by = request.user
                    active_cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
                    has_override = True

                if _restore_category_ancestors(cat, request.user):
                    has_override = True
                
                if has_override:
                    overridden_count += 1
                _restore_category_subtree(cat)
            restored_count += 1

    for file_obj in ProjectFile.objects.filter(pk__in=file_ids, is_in_trash=True).select_related("project", "uploaded_by", "category"):
        is_authorized = (
            request.user.is_admin
            or request.user.is_project_manager
            or file_obj.uploaded_by == request.user
            or (file_obj.project and (
                file_obj.project.is_manager(request.user)
                or file_obj.project.is_incharge(request.user)
                or file_obj.project.members.filter(pk=request.user.pk).exists()
            ))
        )
        if is_authorized:
            with transaction.atomic():
                if _restore_file_with_ancestors(file_obj, request.user):
                    overridden_count += 1
            restored_count += 1

    if restored_count:
        msg = f"{restored_count} selected item(s) restored."
        if overridden_count:
            msg += f" {overridden_count} active folder(s) with conflicting names were overridden."
        messages.success(request, msg)
    else:
        messages.warning(request, "No selected items were restored.")
    
    if trash_cat_id:
        return redirect(f"{reverse('tasks:trash')}?trash_cat_id={trash_cat_id}")
    return redirect("tasks:trash")


@login_required
def category_permanent_delete(request, pk):
    cat = get_object_or_404(FileCategory, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or cat.project.is_manager(request.user)):
        messages.error(request, "Only managers can permanently delete folders.")
        return redirect("tasks:trash")
        
    name = cat.name
    # Capture physical path BEFORE deleting DB record (CASCADE wipes the model)
    phys_path = cat.physical_dir_path
    cat.delete()  # CASCADE deletes all nested subcategories and DB file records

    # Delete the matching physical directory from disk after DB deletion is complete
    if phys_path and os.path.isdir(phys_path):
        try:
            import shutil
            shutil.rmtree(phys_path)
        except Exception:
            pass  # Non-blocking — DB record already permanently removed

    messages.success(request, f"Folder '{name}' permanently deleted.")
    return redirect("tasks:trash")
@login_required
def bug_restore(request, pk):
    bug = get_object_or_404(BugReport, pk=pk)
    # Restore allowed for Admin, PM, Incharge, or Reporter
    is_authorized = (request.user.is_admin or 
                     bug.project.is_manager(request.user) or 
                     bug.project.is_incharge(request.user) or 
                     bug.reported_by == request.user)
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this bug report.")
        return redirect("tasks:trash")
        
    bug.is_in_trash = False
    bug.deleted_at = None
    bug.deleted_by = None
    bug.save()

    if bug.linked_task:
        bug.linked_task.is_in_trash = False
        bug.linked_task.deleted_at = None
        bug.linked_task.deleted_by = None
        bug.linked_task.save()
    messages.success(request, f"Bug report '{bug.title}' restored.")
    return redirect("tasks:trash")


@login_required
def bug_permanent_delete(request, pk):
    bug = get_object_or_404(BugReport, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or bug.project.is_manager(request.user)):
        messages.error(request, "Only managers can permanently delete bug reports.")
        return redirect("tasks:trash")
        
    if bug.linked_task:
        bug.linked_task.delete()
        
    bug.delete()
    messages.success(request, "Bug report permanently deleted from database.")
    return redirect("tasks:trash")
