from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.conf import settings
import io
import os
import zipfile
import json
import random
import string

from django.forms import modelformset_factory
from ..models import Project, Release, ModuleMember, Task, Requirement, ProjectModule, AuditLog, RequirementComment
from testcases.models import TestCase
from ..forms import ReleaseForm, RequirementForm, RequirementCommentForm
from ..decorators import manager_or_admin_required
from ..utils.query_utils import get_visible_tasks_qs
from ..services.release_service import ReleaseService


@login_required
def requirement_bulk_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin 
        or request.user.is_project_manager
        or request.user == project.project_incharge
    ):
        messages.error(request, "Only the project in-charge and admins can manage requirements.")
        return redirect("tasks:project_detail", pk=project.pk)

    RequirementFormSet = modelformset_factory(
        Requirement, form=RequirementForm, extra=1, can_delete=True
    )

    if request.method == "POST":
        formset = RequirementFormSet(request.POST, queryset=Requirement.objects.none())
        if formset.is_valid():
            saved_count = 0
            for form in formset:
                # Skip empty forms or forms marked for deletion
                if form.cleaned_data.get("name") and not form.cleaned_data.get("DELETE"):
                    instance = form.save(commit=False)
                    instance.project = project
                    instance.created_by = request.user
                    # Approval logic
                    is_privileged = project.is_manager(request.user) or project.is_incharge(request.user)
                    instance.is_approved = is_privileged
                    instance.save()
                    form.save_m2m()
                    saved_count += 1
            
            messages.success(request, f"{saved_count} requirements created successfully.")
            return redirect(
                f"{reverse('tasks:project_detail', args=[project.pk])}?view=requirements"
            )
        else:
            messages.warning(request, "Please correct the errors in the requirements grid.")
    else:
        formset = RequirementFormSet(queryset=Requirement.objects.none())

    return render(
        request,
        "projects/requirement_bulk_form.html",
        {"formset": formset, "project": project, "title": "Bulk Add Requirements"},
    )


def release_list(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if request.user.is_authenticated:
        is_member = (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or request.user.is_admin
        )
        is_module_member = ModuleMember.objects.filter(
            module__project=project, user=request.user
        ).exists()
        is_pm_or_admin = (
            request.user.is_admin
            or request.user.is_project_manager
            or project.managers.filter(pk=request.user.pk).exists()
        )
        is_end_user = not (is_member or is_module_member) or request.user.role == "student"
    else:
        is_member = False
        is_module_member = False
        is_pm_or_admin = False
        is_end_user = True

    releases = project.releases.all().order_by("-release_date")
    
    if not is_pm_or_admin:
        releases = releases.filter(status="completed", is_draft=False)

    if is_end_user:
        if request.user.is_authenticated and request.user.role == "student":
            releases = releases.filter(release_type="phase")

    latest_release = releases.filter(is_draft=False, is_prerelease=False).first()

    return render(
        request,
        "releases/release_list.html",
        {
            "project": project,
            "releases": releases,
            "latest_release": latest_release,
            "is_end_user": is_end_user,
        },
    )


@login_required
@manager_or_admin_required
def release_create(request, pk=0):
    project = get_object_or_404(Project, pk=pk) if pk and pk != 0 else None
    form = ReleaseForm(request.POST or None, project=project, user=request.user)

    if request.method == "POST" and form.is_valid():
        release = form.save(commit=False)
        if not project:
            project = form.cleaned_data.get("project")
        release.project, release.author = project, request.user
        release.save()

        # Handle selected files and folders
        selected_files = form.cleaned_data.get("selected_files", [])
        selected_folders = form.cleaned_data.get("selected_folders", [])
        include_subfolders = form.cleaned_data.get("include_subfolders", True)

        from ..models import ReleaseFile
        from files.models import ProjectFile

        final_files = set(selected_files)

        if selected_folders:
            def add_folder_files(folder):
                # Add files in this folder
                final_files.update(ProjectFile.objects.filter(category=folder, project=project, versions__isnull=True))
                if include_subfolders:
                    for child in folder.children.all():
                        add_folder_files(child)

            for folder in selected_folders:
                add_folder_files(folder)

        from ..services.release_service import ReleaseService
        assets_count = ReleaseService.create_release_snapshot(release, request.user, files_to_include=list(final_files))

        # Store selected folders in metadata
        final_folders = set()
        if selected_folders:
            def add_folder_and_subfolders(folder):
                final_folders.add(folder.project_relative_path)
                if include_subfolders:
                    for child in folder.children.all():
                        add_folder_and_subfolders(child)
            for folder in selected_folders:
                add_folder_and_subfolders(folder)
        release.metadata = release.metadata or {}
        release.metadata['selected_folders'] = list(final_folders)
        release.save()

        messages.success(request, f'Release "{release.name}" created successfully with {assets_count} immutable assets.')
        return redirect("tasks:release_detail", pk=release.pk)

    return render(
        request,
        "releases/release_form.html",  # Updated path
        {
            "form": form,
            "project": project,
            "title": "Create Release",
            "root_categories": (
                project.file_categories.filter(parent=None, is_in_trash=False) if project else []
            ),
            "root_files": (
                project.files.filter(category=None, task=None, is_in_trash=False, versions__isnull=True).order_by("original_name") if project else []
            ),
        },
    )


def release_detail(request, pk):
    release = get_object_or_404(Release, pk=pk)
    project = release.project
    
    # If the release is not completed/published, require authentication first
    if release.is_draft or release.status != "completed":
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

    if request.user.is_authenticated:
        is_member = (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or request.user.is_admin
        )
        is_module_member = ModuleMember.objects.filter(
            module__project=project, user=request.user
        ).exists()
        is_end_user = not (is_member or is_module_member) or request.user.role == "student"
        is_pm_or_admin = (
            request.user.is_admin
            or request.user.is_project_manager
            or project.managers.filter(pk=request.user.pk).exists()
        )
    else:
        is_member = False
        is_module_member = False
        is_end_user = True
        is_pm_or_admin = False

    if not is_pm_or_admin and (release.is_draft or release.status != "completed"):
        messages.error(request, "This release is not publicly available yet.")
        return redirect("tasks:release_list", pk=project.pk)

    if is_end_user and release.release_type != "phase" and release.status != "completed":
        messages.error(request, "You only have access to phase releases.")
        return redirect("tasks:release_list", pk=project.pk)

    tasks = release.tasks.all()
    if request.method == "POST" and request.user.is_authenticated and (
        request.user.is_admin
        or project.managers.filter(pk=request.user.pk).exists()
        or request.user == release.author
    ):
        new_status = request.POST.get("status")
        if new_status and new_status in dict(Release.STATUS_CHOICES):
            release.status = new_status
            release.save()
            messages.success(request, f"Release status updated.")
            return redirect("tasks:release_detail", pk=pk)

        if "file" in request.FILES:
            from files.models import ProjectFile, FileCategory

            release_root_cat, _ = FileCategory.objects.get_or_create(
                name="Releases",
                project=project,
                parent=None,
                defaults={"created_by": request.user},
            )
            rel_cat, _ = FileCategory.objects.get_or_create(
                name=release.name,
                project=project,
                parent=release_root_cat,
                defaults={"created_by": request.user},
            )

            for uploaded_file in request.FILES.getlist("file"):
                new_f = ProjectFile(
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                    project=project,
                    release=release,
                    category=rel_cat,
                    uploaded_by=request.user,
                    is_public=True,
                )
                new_f.save()
            messages.success(request, f"File(s) added to release.")
            return redirect("tasks:release_detail", pk=pk)

    kanban = {
        s: tasks.filter(status=s)
        for s in ["todo", "in_progress", "review", "done", "blocked"]
    }

    # Files associated with THIS release
    release_files = release.release_files.select_related('project_file', 'project_file__uploaded_by', 'project_file__category').all()

    is_manager = False
    if request.user.is_authenticated:
        is_manager = (
            request.user.is_admin
            or request.user.is_project_manager
            or project.managers.filter(pk=request.user.pk).exists()
        )

    return render(
        request,
        "releases/release_detail.html",
        {
            "release": release,
            "project": project,
            "kanban": kanban,
            "tasks": tasks,
            "module_versions": release.module_versions.all(),
            "release_files": release_files,
            "is_manager": is_manager,
            "is_member": is_member,
            "is_public_view": (not is_member and release.status == "completed"),
            "pending_delete_request": release.deletion_requests.filter(status='pending').exists(),
        },
    )


@login_required
def requirement_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin 
        or request.user.is_project_manager
        or request.user == project.project_incharge
    ):
        messages.error(request, "Only the project in-charge and admins can manage requirements.")
        return redirect("tasks:project_detail", pk=project.pk)

    module_id = request.GET.get("module")
    initial = {}
    if module_id:
        from ..models import ProjectModule
        initial["module"] = get_object_or_404(ProjectModule, pk=module_id)

    form = RequirementForm(request.POST or None, project=project, initial=initial)
    if request.method == "POST" and form.is_valid():
        req = form.save(commit=False)
        req.project = project
        req.created_by = request.user
        # Approval logic
        is_privileged = project.is_manager(request.user) or project.is_incharge(request.user)
        req.is_approved = is_privileged
        req.save()
        messages.success(request, f'Requirement "{req.name}" created.')
        if module_id:
            return redirect("tasks:module_detail", pk=module_id)
        return redirect(
            f"{reverse('tasks:project_detail', args=[project.pk])}?view=requirements"
        )
    elif request.method == "POST":
        messages.warning(request, "Please correct the errors below.")

    return render(
        request,
        "projects/requirement_form.html",  # Updated path
        {
            "form": form,
            "project": project,
            "action": "Create Requirement",
            "title": "New Requirement",
        },
    )


@login_required
def requirement_detail(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    project = req.project
    
    is_member = (
        project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
    )
    if not is_member:
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")
        
    from testcases.models import TestCase
    from bugs.models import BugReport
    
    tasks = req.tasks.filter(is_in_trash=False)
    test_cases = TestCase.objects.filter(task__requirement=req, is_in_trash=False)
    bugs = BugReport.objects.filter(linked_task__requirement=req, is_in_trash=False)
    comments = req.comments.filter(parent__isnull=True).select_related("author").all()
    comment_form = RequirementCommentForm()
        
    return render(
        request,
        "projects/requirement_detail.html",
        {
            "requirement": req,
            "project": project,
            "tasks": tasks,
            "test_cases": test_cases,
            "bugs": bugs,
            "comments": comments,
            "comment_form": comment_form,
        },
    )


@login_required
def requirement_comment_add(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    project = req.project
    
    is_member = (
        project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
    )
    if not is_member:
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")
        
    if request.method == "POST":
        form = RequirementCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.requirement = req
            comment.author = request.user
            parent_id = request.POST.get("parent_id")
            if parent_id:
                try:
                    comment.parent = RequirementComment.objects.get(pk=parent_id)
                except RequirementComment.DoesNotExist:
                    pass
            comment.save()
            
            # Send Notification to all project members
            from tasks.services.notification_service import NotificationService
            recipients = set(project.members.all()) | set(project.managers.all())
            if project.project_incharge:
                recipients.add(project.project_incharge)
            
            for recipient in recipients:
                if recipient != request.user:
                    NotificationService.create_notification(
                        recipient=recipient,
                        sender=request.user,
                        notification_type="project_update",
                        title=f"New Comment on Requirement: {req.name}",
                        message=f"{request.user.display_name} commented on requirement '{req.name}': {comment.content[:50]}...",
                        project=project,
                    )
            
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Error adding comment.")
            
    return redirect("tasks:requirement_detail", pk=pk)


@login_required
def requirement_edit(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    
    if req.is_in_trash and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "This requirement is in the trash and can only be previewed by Admins or Project Managers.")
        return redirect("tasks:project_detail", pk=req.project.pk)

    project = req.project
    if not (
        request.user.is_admin 
        or request.user in project.managers.all()
        or request.user == project.project_incharge
    ):
        messages.error(request, "Only project managers, in-charge and admins can manage requirements.")
        return redirect("tasks:project_detail", pk=project.pk)

    form = RequirementForm(request.POST or None, instance=req, project=project)
    if request.method == "POST" and form.is_valid():
        req = form.save()
        messages.success(request, f'Requirement "{req.name}" updated.')
        if req.module:
            return redirect("tasks:module_detail", pk=req.module.pk)
        return redirect(
            f"{reverse('tasks:project_detail', args=[project.pk])}?view=requirements"
        )

    return render(
        request,
        "projects/requirement_form.html",  # Updated path
        {
            "form": form,
            "project": project,
            "title": "Edit Requirement",
            "action": "Update Requirement",
        },
    )


@login_required
def requirement_delete(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    project = req.project
    if not (
        request.user.is_admin 
        or request.user.is_project_manager
        or request.user == project.project_incharge
    ):
        messages.error(request, "Only the project in-charge and admins can delete requirements.")
        return redirect("tasks:project_detail", pk=project.pk)

    tasks = req.tasks.all()
    # Test cases are linked to tasks
    test_cases = TestCase.objects.filter(task__in=tasks)
    
    linked_tasks_count = tasks.count()
    linked_tests_count = test_cases.count()

    if request.method == "POST":
        req_title = req.name
        req_pk = req.pk
        now = timezone.now()

        # Audit log before deletion
        AuditLog.objects.create(
            user=request.user,
            action_type="delete",
            module="requirement",
            entity_id=str(req_pk),
            entity_name=req_title,
            details=f"Deleted requirement '{req_title}' (ID: {req_pk}) from project '{project.name}'. "
                    f"Cascaded to {linked_tasks_count} tasks and {linked_tests_count} test cases.",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Cascading soft delete
        tasks.update(is_in_trash=True, deleted_at=now, deleted_by=request.user)
        test_cases.update(is_in_trash=True, deleted_at=now, deleted_by=request.user)
        
        req.is_in_trash = True
        req.deleted_at = now
        req.deleted_by = request.user
        req.save()
        
        messages.success(request, f'Requirement "{req_title}" and its {linked_tasks_count} tasks and {linked_tests_count} test cases moved to trash.')
        return redirect(
            f"{reverse('tasks:project_detail', args=[project.pk])}?view=requirements"
        )

    return render(
        request,
        "projects/requirement_confirm_delete.html",
        {
            "requirement": req,
            "project": project,
            "linked_tasks": tasks,
            "linked_tests": test_cases,
            "linked_tasks_count": linked_tasks_count,
            "linked_tests_count": linked_tests_count,
        },
    )


@login_required
def project_cicd(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not request.user.is_admin:
        if not (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
        ):
            messages.error(request, "You do not have access to this project.")
            return redirect("tasks:project_list")
    pipeline_runs = project.pipeline_runs.all()[:10]
    releases = project.releases.all()
    return render(
        request,
        "releases/project_cicd.html",
        {"project": project, "pipeline_runs": pipeline_runs, "releases": releases},
    )  # Updated path


def release_assets_download(request, pk):
    release = get_object_or_404(Release, pk=pk)
    project = release.project
    
    is_public = (release.status == "completed" and not release.is_draft)
    
    if not is_public:
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
            
        is_member = (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or request.user.is_admin
        )
        if not is_member:
            messages.error(request, "Access denied.")
            return redirect("tasks:project_list")
            
    file_ids = request.POST.getlist("file_ids")
    if not file_ids:
        messages.warning(request, "No files selected.")
        return redirect("tasks:release_detail", pk=pk)
    from ..models import ReleaseFile

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        files = ReleaseFile.objects.filter(pk__in=file_ids, release=release)
        files_added = 0
        for rf in files:
            if rf.file and os.path.exists(rf.file.path):
                zip_file.write(rf.file.path, arcname=rf.get_project_relative_path())
                files_added += 1
    if files_added == 0:
        messages.error(request, "Could not find files.")
        return redirect("tasks:release_detail", pk=pk)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="assets_{release.pk}.zip"'
    return response


@login_required
@manager_or_admin_required
def release_edit(request, pk):
    release = get_object_or_404(Release, pk=pk)
    project = release.project
    
    if release.is_locked:
        messages.error(request, "This release is locked and cannot be edited.")
        return redirect("tasks:release_detail", pk=release.pk)

    form = ReleaseForm(request.POST or None, instance=release, project=project)
    if request.method == "POST" and form.is_valid():
        release = form.save()
        
        # Handle selected files and folders (syncing)
        selected_files = form.cleaned_data.get("selected_files", [])
        selected_folders = form.cleaned_data.get("selected_folders", [])
        include_subfolders = form.cleaned_data.get("include_subfolders", True)

        from ..models import ReleaseFile
        from files.models import ProjectFile

        final_files = set(selected_files)

        if selected_folders:
            def add_folder_files(folder):
                final_files.update(ProjectFile.objects.filter(category=folder, project=project, versions__isnull=True))
                if include_subfolders:
                    for child in folder.children.all():
                        add_folder_files(child)

            for folder in selected_folders:
                add_folder_files(folder)

        if not release.is_locked:
            from ..services.release_service import ReleaseService
            # Clear old and re-snapshot
            release.release_files.all().delete()
            ReleaseService.create_release_snapshot(release, request.user, files_to_include=list(final_files))

        # Store selected folders in metadata
        final_folders = set()
        if selected_folders:
            def add_folder_and_subfolders(folder):
                final_folders.add(folder.project_relative_path)
                if include_subfolders:
                    for child in folder.children.all():
                        add_folder_and_subfolders(child)
            for folder in selected_folders:
                add_folder_and_subfolders(folder)
        release.metadata = release.metadata or {}
        release.metadata['selected_folders'] = list(final_folders)
        release.save()

        messages.success(request, f'Release "{release.name}" updated.')
        return redirect("tasks:release_detail", pk=release.pk)
    return render(
        request,
        "releases/release_form.html",
        {
            "form": form,
            "project": project,
            "title": "Edit Release",
            "release": release,
            "root_categories": project.file_categories.filter(parent=None, is_in_trash=False) if project else [],
            "root_files": (
                project.files.filter(category=None, task=None, is_in_trash=False, versions__isnull=True).order_by("original_name") if project else []
            ),
        },
    )


@login_required
@manager_or_admin_required
def release_delete(request, pk):
    release = get_object_or_404(Release, pk=pk)
    project = release.project
    
    # Security: Prevent accidental deletion of completed releases
    if release.status == 'completed' and not request.user.is_admin:
        messages.error(request, "Only administrators can delete a completed release.")
        return redirect("tasks:release_detail", pk=release.pk)

    if request.method == "POST":
        # Check one more time before final deletion
        if release.status == 'completed' and not (request.user.is_admin or request.user.is_project_manager):
             return redirect("tasks:release_detail", pk=release.pk)
             
        release.delete()
        messages.success(request, "Release deleted.")
        return redirect("tasks:release_list", pk=project.pk)
        
    return render(
        request, "projects/confirm_delete.html", {
            "obj": release, 
            "obj_type": "Release",
            "warning": "Warning: This will permanently remove all immutable snapshots associated with this release." if release.status == 'completed' else ""
        }
    )


def release_download(request, pk):
    release = get_object_or_404(Release, pk=pk)
    project = release.project

    is_public = (release.status == "completed" and not release.is_draft)
    if not is_public:
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        is_member = (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or request.user.is_admin
        )
        if not is_member:
            messages.error(request, "Access denied.")
            return redirect("tasks:project_list")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for rf in release.release_files.all():
            if rf.file and os.path.exists(rf.file.path):
                zip_file.write(rf.file.path, arcname=rf.get_project_relative_path())
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = (
        f"attachment; filename={project.name}_{release.name}.zip"
    )
    return response


def global_release_list(request):
    search_query = request.GET.get("q", "")
    
    is_pm_or_admin = False
    if request.user.is_authenticated:
        is_pm_or_admin = request.user.is_admin or request.user.is_project_manager

    project_releases = []
    projects_query = Project.objects.all()
    if search_query:
        projects_query = projects_query.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
        
    for project in projects_query:
        has_draft_access = False
        if request.user.is_authenticated:
            if is_pm_or_admin:
                has_draft_access = True
            elif project.members.filter(pk=request.user.pk).exists() or project.managers.filter(pk=request.user.pk).exists():
                has_draft_access = True
                
        releases = Release.objects.filter(project=project)
        if not has_draft_access:
            releases = releases.filter(status="completed", is_draft=False)
            
        releases = releases.order_by("-release_date")
        if releases.exists():
            project_releases.append({"project": project, "releases": releases})
            
    return render(
        request,
        "releases/global_release_list.html",
        {"project_releases": project_releases, "search_query": search_query},
    )


@login_required
@login_required
def requirement_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")

    report_format = request.GET.get("format", "pdf")
    template_type = request.GET.get("template", "srs")
    requirements = project.requirements.filter(is_in_trash=False).order_by("req_id")

    from ..services.report_engine import ReportEngine
    content = ReportEngine.generate_requirement_report(project, requirements, format=report_format, template_type=template_type)

    content_type_map = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pdf': 'application/pdf',
        'md': 'text/markdown',
    }
    
    response = HttpResponse(content, content_type=content_type_map.get(report_format, 'application/pdf'))
    extension = report_format if report_format in ['docx', 'xlsx', 'md'] else 'pdf'
    response["Content-Disposition"] = f'attachment; filename="{template_type.upper()}_{project.project_id}.{extension}"'
    return response

@login_required
def task_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")

    report_format = request.GET.get("format", "pdf")
    tasks = Task.objects.filter(project=project).order_by("task_id")

    from ..services.report_engine import ReportEngine
    content = ReportEngine.generate_task_report(project, tasks, format=report_format)

    content_type_map = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pdf': 'application/pdf',
        'md': 'text/markdown',
    }
    
    response = HttpResponse(content, content_type=content_type_map.get(report_format, 'application/pdf'))
    extension = report_format if report_format in ['docx', 'xlsx', 'md'] else 'pdf'
    response["Content-Disposition"] = f'attachment; filename="TaskReport_{project.project_id}.{extension}"'
    return response


def release_asset_download(request, pk):
    from ..models import ReleaseFile
    asset = get_object_or_404(ReleaseFile, pk=pk)
    release = asset.release
    project = release.project

    is_public = (release.status == "completed" and not release.is_draft)
    if not is_public:
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        is_member = (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or request.user.is_admin
        )
        if not is_member:
            messages.error(request, "Access denied.")
            return redirect("tasks:project_list")

    if not asset.file:
        messages.error(request, "File not found in this release.")
        return redirect("tasks:release_detail", pk=release.pk)

    response = HttpResponse(asset.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{asset.original_name}"'
    return response


@login_required
def release_compare(request, pk):
    release_b = get_object_or_404(Release, pk=pk)
    project = release_b.project
    
    compare_with_id = request.GET.get('with')
    release_a = None
    diff = None
    
    if compare_with_id:
        release_a = get_object_or_404(Release, pk=compare_with_id)
        from ..services.release_service import ReleaseService
        diff = ReleaseService.compare_releases(release_a, release_b)
        
    other_releases = project.releases.exclude(pk=release_b.pk).order_by('-release_date')
    
    return render(request, "releases/release_compare.html", {
        'project': project,
        'release_a': release_a,
        'release_b': release_b,
        'diff': diff,
        'other_releases': other_releases,
    })


@login_required
@manager_or_admin_required
def release_restore(request, pk):
    """
    Restores all files from a release into the project's live working set as new versions.
    """
    release = get_object_or_404(Release, pk=pk)
    project = release.project
    
    if request.method == "POST":
        from files.models import ProjectFile
        from django.core.files.base import ContentFile
        
        restored_count = 0
        for asset in release.release_files.all():
            if not asset.file: continue
            
            # Find latest live version of this file
            live_file = ProjectFile.objects.filter(
                project=project, 
                original_name=asset.original_name,
                versions__isnull=True
            ).first()
            
            # Create new version
            new_v = ProjectFile(
                project=project,
                original_name=asset.original_name,
                category=live_file.category if live_file else None,
                uploaded_by=request.user,
                parent_file=live_file,
                version=(live_file.version + 1) if live_file else 1,
                is_public=True
            )
            
            # Copy content from release snapshot
            try:
                asset.file.open('rb')
                new_v.file.save(asset.original_name, ContentFile(asset.file.read()), save=False)
                new_v.save()
                restored_count += 1
            except Exception:
                continue
                
        messages.success(request, f"Successfully restored {restored_count} files from release {release.version or release.name}.")
        return redirect("tasks:project_detail", pk=project.pk)

    return render(request, "releases/release_restore_confirm.html", {
        "release": release,
        "project": project
    })
        
@login_required
@manager_or_admin_required
def release_publish(request, pk):
    release = get_object_or_404(Release, pk=pk)
    if request.method == "POST":
        ReleaseService.publish_release(release, request.user)
        messages.success(request, f"Release {release.version or release.name} has been published and locked.")
    return redirect("tasks:release_detail", pk=release.pk)


@login_required
@manager_or_admin_required
def release_asset_upload(request, pk):
    release = get_object_or_404(Release, pk=pk)
    if release.is_locked:
        messages.error(request, "Cannot add assets to a locked release.")
        return redirect("tasks:release_detail", pk=release.pk)
        
    from ..forms.release_forms import ReleaseAssetUploadForm
    form = ReleaseAssetUploadForm(request.POST or None, request.FILES or None)
    
    if request.method == "POST" and form.is_valid():
        asset_file = request.FILES.get('asset_file')
        ReleaseService.add_asset_to_release(release, asset_file, request.user)
        messages.success(request, f"Asset '{asset_file.name}' uploaded successfully.")
        return redirect("tasks:release_detail", pk=release.pk)
        
    return render(request, "releases/asset_upload.html", {"release": release, "form": form})


@login_required
def release_deletion_request(request, pk):
    release = get_object_or_404(Release, pk=pk)
    if release.deletion_requests.filter(status='pending').exists():
        messages.warning(request, "A deletion request is already pending for this release.")
        return redirect("tasks:release_detail", pk=release.pk)

    from ..forms.release_forms import ReleaseDeletionRequestForm
    from ..models import ReleaseLog
    
    form = ReleaseDeletionRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        req = form.save(commit=False)
        req.release = release
        req.requested_by = request.user
        req.save()
        
        ReleaseLog.objects.create(
            release=release,
            user=request.user,
            action='deletion_requested',
            details=f"Reason: {req.reason}"
        )
        
        # Send notification to admins
        try:
            from accounts.models import User
            from tasks.services.notification_service import NotificationService
            from django.db.models import Q
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins:
                NotificationService.create_notification(
                    recipient=admin,
                    sender=request.user,
                    notification_type='project_update',
                    title='Release Deletion Request',
                    message=f"A deletion request for release '{release.name}' was submitted by {request.user.username}.",
                    project=release.project
                )
        except Exception as e:
            print(f"Error sending notifications to admins: {e}")
        
        messages.success(request, "Deletion request submitted for admin approval.")
        return redirect("tasks:release_detail", pk=release.pk)
        
    return render(request, "releases/deletion_request.html", {"release": release, "form": form})


@login_required
def admin_deletion_requests(request):
    if not request.user.is_admin:
        messages.error(request, "Access denied.")
        return redirect("dashboard")
        
    from ..models import ReleaseDeletionRequest, ProjectDeletionRequest
    release_requests = ReleaseDeletionRequest.objects.filter(status='pending').select_related('release', 'requested_by')
    project_requests = ProjectDeletionRequest.objects.filter(status='pending').select_related('project', 'requested_by')
    
    return render(request, "releases/admin_deletion_requests.html", {
        "release_requests": release_requests,
        "project_requests": project_requests
    })


@login_required
def resolve_deletion_request(request, req_type, pk):
    if not request.user.is_admin:
        messages.error(request, "Access denied.")
        return redirect("dashboard")
        
    from ..models import ReleaseDeletionRequest, ProjectDeletionRequest, ReleaseLog
    from django.utils import timezone
    
    if req_type == 'release':
        req = get_object_or_404(ReleaseDeletionRequest, pk=pk)
    else:
        req = get_object_or_404(ProjectDeletionRequest, pk=pk)
        
    action = request.POST.get('action') # 'approve' or 'reject'
    
    if request.method == "POST":
        if action == 'approve':
            if req_type == 'release':
                release = req.release
                project_id = release.project.pk
                ReleaseLog.objects.create(
                    release=release,
                    user=request.user,
                    action='deletion_approved',
                    details=f"Approved by {request.user.username}. Admin Notes: {request.POST.get('admin_notes')}"
                )
                req.status = 'approved'
                req.save()
                release.delete()
                messages.success(request, f"Release deleted permanently.")
                return redirect("tasks:project_detail", pk=project_id)
            else:
                project = req.project
                req.status = 'approved'
                req.save()
                project.delete()
                messages.success(request, f"Project deleted permanently.")
                return redirect("tasks:project_list")
        else:
            req.status = 'rejected'
            req.save()
            if req_type == 'release':
                ReleaseLog.objects.create(
                    release=req.release,
                    user=request.user,
                    action='deletion_rejected',
                    details=f"Rejected by {request.user.username}. Admin Notes: {request.POST.get('admin_notes')}"
                )
            messages.info(request, "Deletion request rejected.")
            return redirect("tasks:admin_deletion_requests")

@login_required
def rtm_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")

    report_format = request.GET.get("format", "html")
    requirements = project.requirements.filter(is_in_trash=False).prefetch_related(
        'tasks', 
        'tasks__test_cases'
    ).order_by('req_id')

    if report_format != "html":
        from ..services.report_engine import ReportEngine
        content = ReportEngine.generate_requirement_report(project, requirements, format=report_format)
        content_type_map = {
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf',
            'md': 'text/markdown',
        }
        response = HttpResponse(content, content_type=content_type_map.get(report_format, 'application/pdf'))
        extension = report_format if report_format in ['docx', 'xlsx', 'md'] else 'pdf'
        response["Content-Disposition"] = f'attachment; filename="RTM_{project.project_id}.{extension}"'
        return response

    rtm_data = []
    for req in requirements:
        tasks = req.tasks.filter(is_in_trash=False)
        if not tasks:
            rtm_data.append({
                'req': req,
                'task': None,
                'test': None,
                'status': 'Not Mapped'
            })
        else:
            for task in tasks:
                tests = task.test_cases.filter(is_in_trash=False)
                if not tests:
                    rtm_data.append({
                        'req': req,
                        'task': task,
                        'test': None,
                        'status': 'Tasks Defined'
                    })
                else:
                    for test in tests:
                        rtm_data.append({
                            'req': req,
                            'task': task,
                            'test': test,
                            'status': test.get_status_display()
                        })

    return render(request, "reports/rtm_matrix.html", {
        "project": project,
        "rtm_data": rtm_data
    })

@login_required
def test_case_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")

    report_format = request.GET.get("format", "pdf")
    test_cases = project.test_cases.filter(is_in_trash=False).order_by("test_id")

    from ..services.report_engine import ReportEngine
    content = ReportEngine.generate_test_report(project, test_cases, format=report_format)

    content_type_map = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pdf': 'application/pdf',
        'md': 'text/markdown',
    }
    
    response = HttpResponse(content, content_type=content_type_map.get(report_format, 'application/pdf'))
    extension = report_format if report_format in ['docx', 'xlsx', 'md'] else 'pdf'
    response["Content-Disposition"] = f'attachment; filename="QAReport_{project.project_id}.{extension}"'
    return response

@login_required
def requirement_approve(request, pk):
    req = get_object_or_404(Requirement, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or req.project.is_manager(request.user)):
        messages.error(request, "Only managers can approve requirements.")
        return redirect("tasks:rtm_view", pk=req.project.pk)
        
    req.is_approved = True
    req.save()
    messages.success(request, f"Requirement '{req.name}' has been approved.")
    return redirect("tasks:rtm_view", pk=req.project.pk)
