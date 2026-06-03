from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse

from accounts.models import User
from ..models import Project, Task, Requirement
from bugs.models import BugReport
from testcases.models import TestCase
from ..forms import ProjectForm, ProjectEditForm, ProjectSettingsForm
from ..decorators import manager_or_admin_required
from ..services.project_service import ProjectService
from ..utils.query_utils import get_visible_tasks_qs


@login_required
def project_list(request):
    user = request.user
    module_filter = request.GET.get("module", "")
    status_filter = request.GET.get("status", "")
    search = request.GET.get("q", "")
    deletion_requested = request.GET.get("deletion_requested", "")

    if user.is_admin:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(managers=user) | Q(members=user) | Q(project_incharge=user)
        ).distinct()

    show_archived = request.GET.get("archived", "")
    if show_archived == "1":
        projects = projects.filter(is_archived=True)
    else:
        projects = projects.filter(is_archived=False)

    if deletion_requested:
        projects = projects.filter(
            Q(deletion_requested_by_admin=True) | Q(deletion_requested_by_pm=True)
        )

    if module_filter:
        projects = projects.filter(module=module_filter)
    if status_filter == "in_progress":
        projects = projects.exclude(status__in=["completed", "cancelled"])
    elif status_filter:
        projects = projects.filter(status=status_filter)
    if search:
        projects = projects.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    paginator = Paginator(projects.order_by("-created_at"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "projects/project_list.html",  # Updated path
        {
            "projects": page_obj,
            "page_obj": page_obj,
            "module_choices": Project.MODULE_CHOICES,
            "status_choices": Project.STATUS_CHOICES,
            "module_filter": module_filter,
            "status_filter": status_filter,
            "search": search,
        },
    )


@login_required
@manager_or_admin_required
def project_create(request):
    form = ProjectForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.created_by = request.user
        project.save()
        form.save_m2m()

        budget_amt = form.cleaned_data.get("budget")
        if budget_amt is not None:
            from finance.models import Budget

            Budget.objects.create(project=project, total_amount=budget_amt)

        # Use ProjectService for initialization
        ProjectService.initialize_project_folders(project, request.user)
        ProjectService.notify_project_assignment(project, request.user)

        messages.success(request, f'Project "{project.name}" created successfully.')
        return redirect("tasks:project_detail", pk=project.pk)

    return render(
        request,
        "projects/project_form.html",  # Updated path
        {"form": form, "title": "New Project", "action": "Create Project"},
    )


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    tasks = (
        get_visible_tasks_qs(request.user, project.tasks.exclude(task_type="bug"))
        .select_related("created_by")
        .prefetch_related("assignees")
    )

    kanban = {
        "todo": tasks.filter(status="todo"),
        "in_progress": tasks.filter(status="in_progress"),
        "review": tasks.filter(status="review"),
        "done": tasks.filter(status="done"),
        "blocked": tasks.filter(status="blocked"),
    }

    # Filters
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    assignee_filter = request.GET.get("assignee", "")
    type_filter = request.GET.get("type", "")
    view_mode = request.GET.get("view", "list")

    filtered_tasks = tasks
    if status_filter:
        filtered_tasks = filtered_tasks.filter(status=status_filter)
    if priority_filter:
        filtered_tasks = filtered_tasks.filter(priority=priority_filter)
    if assignee_filter:
        filtered_tasks = filtered_tasks.filter(assignees__id=assignee_filter)
    if type_filter:
        filtered_tasks = filtered_tasks.filter(task_type=type_filter)

    # Bugs Visibility Logic
    if request.user.is_admin or project.managers.filter(pk=request.user.pk).exists() or request.user.is_project_manager:
        bugs = project.bug_reports.filter(is_in_trash=False)
    else:
        # Members only see bugs they reported or bugs assigned to them
        bugs = project.bug_reports.filter(
            Q(reported_by=request.user) | Q(assignees=request.user),
            is_in_trash=False
        ).distinct()

    resource_view = request.GET.get("resource_view", "tree")
    if resource_view == "grid":
        resource_view = "tree"
    repo_cat_id = request.GET.get("repo_cat_id")
    current_repo_cat = None
    if repo_cat_id:
        from files.models import FileCategory

        current_repo_cat = get_object_or_404(
            FileCategory, pk=repo_cat_id, project=project
        )

    from files.models import FileCategory, FileComment
    from files.forms import FileCommentForm

    active_resource_cat = current_repo_cat
    if not active_resource_cat:
        active_resource_cat = FileCategory.objects.filter(project=project, name="resources").first()

    resource_comment_form = FileCommentForm(prefix="res_comm")
    if request.method == "POST" and "submit_resource_comment" in request.POST:
        resource_comment_form = FileCommentForm(request.POST, prefix="res_comm")
        if resource_comment_form.is_valid() and active_resource_cat:
            c = resource_comment_form.save(commit=False)
            c.category = active_resource_cat
            c.author = request.user
            c.save()
            messages.success(request, "Comment added to resource folder.")
            redirect_url = reverse("tasks:project_detail", kwargs={"pk": project.pk}) + "?view=resources"
            if repo_cat_id:
                redirect_url += f"&resource_view={resource_view}&repo_cat_id={repo_cat_id}"
            else:
                redirect_url += f"&resource_view={resource_view}"
            return redirect(redirect_url)

    resource_comments = []
    if active_resource_cat:
        resource_comments = active_resource_cat.comments.select_related("author").all()

    # Test Case Stats
    test_cases = project.test_cases.filter(is_in_trash=False)
    tc_total = test_cases.count()
    tc_passed = test_cases.filter(status="passed").count()
    tc_failed = test_cases.filter(status="failed").count()
    tc_pending = test_cases.filter(status="pending").count()
    tc_retest = test_cases.filter(status="retest").count()
    tc_percentage = int((tc_passed / tc_total * 100)) if tc_total > 0 else 0

    requirements = project.requirements.filter(is_in_trash=False)

    return render(
        request,
        "projects/project_detail.html",  # Updated path
        {
            "project": project,
            "tasks": filtered_tasks,
            "requirements": requirements,
            "test_cases": test_cases,
            "notes": project.kb_notes.filter(is_in_trash=False),
            "bugs": bugs if view_mode == "bugs" else bugs[:5],
            "kanban": kanban,
            "members": project.members.all(),
            "releases": project.releases.all(),
            "status_choices": Task.STATUS_CHOICES,
            "priority_choices": Task.PRIORITY_CHOICES,
            "type_choices": Task.TYPE_CHOICES,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "assignee_filter": assignee_filter,
            "type_filter": type_filter,
            "view_mode": view_mode,
            "resource_view": resource_view,
            "root_categories": project.file_categories.filter(parent=None, is_in_trash=False),
            "current_repo_cat": current_repo_cat,
            "tc_stats": {
                "total": tc_total,
                "passed": tc_passed,
                "failed": tc_failed,
                "pending": tc_pending,
                "retest": tc_retest,
                "percentage": tc_percentage,
            },
            "is_pm": project.managers.filter(pk=request.user.pk).exists() or request.user.is_admin or request.user.is_project_manager,
            "is_incharge": project.project_incharge == request.user,
            "resource_comments": resource_comments,
            "resource_comment_form": resource_comment_form,
            "active_resource_cat": active_resource_cat,
        },
    )


@login_required
@manager_or_admin_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # All Project Managers can edit all projects

    old_members = set(project.members.values_list("pk", flat=True))
    form = ProjectEditForm(request.POST or None, instance=project, user=request.user)

    if request.method == "POST" and form.is_valid():
        project = form.save()
        new_members = set(project.members.values_list("pk", flat=True))
        added_pks = new_members - old_members

        from ..services.notification_service import NotificationService

        for member in User.objects.filter(pk__in=added_pks):
            NotificationService.create_notification(
                member,
                request.user,
                "project_update",
                f"You were added to project: {project.name}",
                f'{request.user.display_name} added you as a member of "{project.name}".',
                project=project,
            )
        messages.success(request, f'Project "{project.name}" updated.')
        return redirect("tasks:project_detail", pk=project.pk)

    return render(
        request,
        "projects/project_edit.html",  # Updated path
        {
            "form": form,
            "title": f"Edit Project — {project.name}",
            "project": project,
        },
    )


@login_required
def project_settings(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # Check permissions: Admin, Global PM, Project-specific Manager, or Project Incharge
    is_manager = project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user

    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or is_manager
        or is_incharge
    ):
        messages.error(request, "You do not have permission to access project settings.")
        return redirect("tasks:project_detail", pk=pk)

    if request.method == "POST":
        form = ProjectSettingsForm(
            request.POST, request.FILES, instance=project, user=request.user
        )
        if form.is_valid():
            try:
                project = form.save()
                messages.success(request, f'Project settings for "{project.name}" updated successfully.')
                return redirect("tasks:project_settings", pk=project.pk)
            except Exception as e:
                messages.error(request, f"System error saving settings: {str(e)}")
        else:
            if not form.errors:
                messages.error(request, "The form is invalid but no specific field errors were reported. Please check all fields.")
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = field.replace('_', ' ').capitalize()
                    messages.error(request, f"{field_name}: {error}")
    else:
        form = ProjectSettingsForm(instance=project, user=request.user)

    return render(
        request,
        "projects/project_settings.html",  # Updated path
        {
            "form": form,
            "title": f"Settings — {project.name}",
            "project": project,
            "tasks": project.tasks.filter(is_in_trash=False).exclude(task_type="bug"),
            "requirements": project.requirements.filter(is_in_trash=False),
            "test_cases": project.test_cases.filter(is_in_trash=False),
            "bugs": project.bug_reports.filter(is_in_trash=False),
        },
    )


@login_required
@manager_or_admin_required
def project_members(request, pk):
    project = get_object_or_404(Project, pk=pk)
    all_users = User.objects.filter(is_active=True).order_by("first_name", "username")
    current_member_ids = set(project.members.values_list("pk", flat=True))

    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        if action and user_id:
            target = get_object_or_404(User, pk=user_id)
            if action == "add":
                project.members.add(target)
                from ..services.notification_service import NotificationService

                NotificationService.create_notification(
                    target,
                    request.user,
                    "project_update",
                    f"Added to project: {project.name}",
                    f'{request.user.display_name} added you to project "{project.name}".',
                    project=project,
                )
                messages.success(
                    request, f"{target.display_name} added to the project."
                )
            elif action == "remove":
                if project.managers.filter(pk=target.pk).exists():
                    messages.error(
                        request, "Cannot remove the project manager from members."
                    )
                else:
                    project.members.remove(target)
                    messages.success(
                        request, f"{target.display_name} removed from the project."
                    )
        return redirect("tasks:project_members", pk=pk)

    return render(
        request,
        "projects/project_members.html",  # Updated path
        {
            "project": project,
            "all_users": all_users,
            "current_member_ids": current_member_ids,
        },
    )


@login_required
@manager_or_admin_required
def project_delete(request, pk):
    from datetime import timedelta
    from django.utils import timezone
    from ..services.project_service import ProjectService

    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action", "request_deletion")

        if action in ["request_deletion", "cancel_deletion"]:
            msg = ProjectService.handle_deletion_request(project, request.user, action)
            if msg:
                messages.info(request, msg)

        elif action == "approve_deletion":
            if (request.user.is_admin and project.deletion_requested_by_pm) or (
                request.user.is_project_manager
                and project.managers.filter(pk=request.user.pk).exists()
                and project.deletion_requested_by_admin
            ):
                project.delete()
                messages.success(request, f'Project "{project.name}" fully deleted.')
                return redirect("tasks:project_list")

        elif action == "force_delete":
            if (
                request.user.is_admin
                and project.deletion_requested_by_admin
                and project.deletion_requested_at
            ):
                if timezone.now() > project.deletion_requested_at + timedelta(days=30):
                    project.delete()
                    messages.success(
                        request, f'Project "{project.name}" was force deleted.'
                    )
                    return redirect("tasks:project_list")
                else:
                    messages.error(
                        request,
                        "You can only force delete after 30 days of requesting.",
                    )

        return redirect("tasks:project_list")

    can_force_delete = False
    if (
        request.user.is_admin
        and project.deletion_requested_by_admin
        and project.deletion_requested_at
    ):
        if timezone.now() > project.deletion_requested_at + timedelta(days=30):
            can_force_delete = True

    return render(
        request,
        "projects/confirm_delete.html",
        {"obj": project, "obj_type": "Project", "can_force_delete": can_force_delete},
    )


@login_required
@manager_or_admin_required
def project_archive_toggle(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.is_manager(request.user):
        messages.error(request, "Permission denied.")
        return redirect("tasks:project_detail", pk=pk)

    project.is_archived = not project.is_archived
    if project.is_archived:
        project.status = "archived"
    else:
        # If unarchiving, set back to 'active' if it was archived
        if project.status == "archived":
            project.status = "active"
    
    project.save()
    action_str = "archived" if project.is_archived else "unarchived"
    messages.success(request, f'Project "{project.name}" has been {action_str}.')
    
    if project.is_archived:
        return redirect("tasks:project_list")
    return redirect("tasks:project_detail", pk=pk)




@login_required
def project_task_list(request, pk):
    """Dedicated task list page for a specific project."""
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "")

    tasks = (
        get_visible_tasks_qs(request.user, project.tasks.exclude(task_type="bug"))
        .select_related("created_by")
        .prefetch_related("assignees")
    )

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if type_filter:
        tasks = tasks.filter(task_type=type_filter)
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    paginator = Paginator(tasks.order_by("-updated_at"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    is_pm = (
        project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
        or request.user.is_project_manager
    )

    return render(
        request,
        "projects/project_task_list.html",
        {
            "project": project,
            "tasks": page_obj,
            "page_obj": page_obj,
            "status_choices": Task.STATUS_CHOICES,
            "priority_choices": Task.PRIORITY_CHOICES,
            "type_choices": Task.TYPE_CHOICES,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "type_filter": type_filter,
            "search": search,
            "is_pm": is_pm,
        },
    )


@login_required
def project_requirement_list(request, pk):
    """Dedicated requirements list page for a specific project."""
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "")

    requirements = project.requirements.filter(is_in_trash=False)

    if status_filter:
        requirements = requirements.filter(status=status_filter)
    if priority_filter:
        requirements = requirements.filter(priority=priority_filter)
    if type_filter:
        requirements = requirements.filter(requirement_type=type_filter)
    if search:
        requirements = requirements.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    paginator = Paginator(requirements.order_by("-created_at"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    is_pm = (
        project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
        or request.user.is_project_manager
    )

    return render(
        request,
        "projects/project_requirement_list.html",
        {
            "project": project,
            "requirements": page_obj,
            "page_obj": page_obj,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "type_filter": type_filter,
            "search": search,
            "is_pm": is_pm,
            "requirement_statuses": Requirement.STATUS_CHOICES,
            "requirement_priorities": Requirement.PRIORITY_CHOICES,
            "requirement_types": Requirement.TYPE_CHOICES,
        },
    )


@login_required
def project_bug_list(request, pk):
    """Dedicated bug reports page for a specific project."""
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    status_filter = request.GET.get("status", "")
    severity_filter = request.GET.get("severity", "")
    search = request.GET.get("q", "")

    is_pm = (
        project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
        or request.user.is_project_manager
    )

    if is_pm:
        bugs = project.bug_reports.filter(is_in_trash=False)
    else:
        bugs = project.bug_reports.filter(
            Q(reported_by=request.user) | Q(assignees=request.user),
            is_in_trash=False,
        ).distinct()

    if status_filter:
        bugs = bugs.filter(status=status_filter)
    if severity_filter:
        bugs = bugs.filter(severity=severity_filter)
    if search:
        bugs = bugs.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    paginator = Paginator(bugs.order_by("-created_at"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/project_bug_list.html",
        {
            "project": project,
            "bugs": page_obj,
            "page_obj": page_obj,
            "status_filter": status_filter,
            "severity_filter": severity_filter,
            "search": search,
            "is_pm": is_pm,
            "bug_statuses": BugReport.STATUS_CHOICES,
            "bug_severities": BugReport.SEVERITY_CHOICES,
        },
    )
