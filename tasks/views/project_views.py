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
    # Fetch current authenticated user
    user = request.user
    # Extract query parameters for category, status, search string, and delete flags
    module_filter = request.GET.get("module", "")
    status_filter = request.GET.get("status", "")
    search = request.GET.get("q", "")
    deletion_requested = request.GET.get("deletion_requested", "")

    # Admins can see all projects in the system
    if user.is_admin:
        projects = Project.objects.all()
    else:
        # Non-admins can only see projects where they are assigned as manager, member, or incharge
        projects = Project.objects.filter(
            Q(managers=user) | Q(members=user) | Q(project_incharge=user)
        ).distinct()

    # Filter by archive status. Default to showing non-archived projects
    show_archived = request.GET.get("archived", "")
    if show_archived == "1":
        projects = projects.filter(is_archived=True)
    else:
        projects = projects.filter(is_archived=False)

    # Filter projects that have pending deletion requests by PM or Admin
    if deletion_requested:
        projects = projects.filter(
            Q(deletion_requested_by_admin=True) | Q(deletion_requested_by_pm=True)
        )

    # Filter by specific project category modules
    if module_filter:
        projects = projects.filter(module=module_filter)
        
    # Exclude completed/cancelled if status filter is in_progress
    if status_filter == "in_progress":
        projects = projects.exclude(status__in=["completed", "cancelled"])
    elif status_filter:
        projects = projects.filter(status=status_filter)
        
    # Perform case-insensitive containment lookup across project names and descriptions
    if search:
        projects = projects.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    # Paginate list displaying 10 projects per page
    paginator = Paginator(projects.order_by("-created_at"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Render template passing the pagination block and choice constraints
    return render(
        request,
        "projects/project_list.html",
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
    # Instantiate project form passing user for manager validation
    form = ProjectForm(request.POST or None, request.FILES or None, user=request.user)
    # Validate form submission parameters
    if request.method == "POST" and form.is_valid():
        # Build project record but do not commit yet
        project = form.save(commit=False)
        # Record currently logged-in user as the creator
        project.created_by = request.user
        # Write to database
        project.save()
        # Save many-to-many relationships (members, managers)
        form.save_m2m()

        # If a budget amount is provided, automatically instantiate budget records
        budget_amt = form.cleaned_data.get("budget")
        if budget_amt is not None:
            from finance.models import Budget

            # Create corresponding Budget tracker entry for the project
            Budget.objects.create(project=project, total_amount=budget_amt)

        # Call service layer to initialize folder architecture on disk/media
        ProjectService.initialize_project_folders(project, request.user)
        # Notify added managers and members via the notifications hub
        ProjectService.notify_project_assignment(project, request.user)

        # Display success banner and redirect to details page
        messages.success(request, f'Project "{project.name}" created successfully.')
        return redirect("tasks:project_detail", pk=project.pk)

    return render(
        request,
        "projects/project_form.html",  # Updated path
        {"form": form, "title": "New Project", "action": "Create Project"},
    )


@login_required
def project_detail(request, pk):
    # Retrieve project or raise 404
    project = get_object_or_404(Project, pk=pk)

    # Secure detail view: restrict access to admins, assigned members, managers, or project incharge
    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    # Fetch non-bug tasks with select_related/prefetch_related to avoid N+1 queries
    tasks = (
        get_visible_tasks_qs(request.user, project.tasks.exclude(task_type="bug"))
        .select_related("created_by")
        .prefetch_related("assignees")
    )

    # Construct Kanban dictionary groupings based on status fields
    kanban = {
        "todo": tasks.filter(status="todo"),
        "in_progress": tasks.filter(status="in_progress"),
        "review": tasks.filter(status="review"),
        "done": tasks.filter(status="done"),
        "blocked": tasks.filter(status="blocked"),
    }

    # Extract UI filter settings from request GET variables
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    assignee_filter = request.GET.get("assignee", "")
    type_filter = request.GET.get("type", "")
    view_mode = request.GET.get("view", "list")

    # Filter tasks dynamically based on UI selections
    filtered_tasks = tasks
    if status_filter:
        filtered_tasks = filtered_tasks.filter(status=status_filter)
    if priority_filter:
        filtered_tasks = filtered_tasks.filter(priority=priority_filter)
    if assignee_filter:
        filtered_tasks = filtered_tasks.filter(assignees__id=assignee_filter)
    if type_filter:
        filtered_tasks = filtered_tasks.filter(task_type=type_filter)

    # Bugs Visibility logic: Admins/PMs see all bugs; regular members see only reported/assigned bugs
    if request.user.is_admin or project.managers.filter(pk=request.user.pk).exists() or request.user.is_project_manager:
        bugs = project.bug_reports.filter(is_in_trash=False)
    else:
        # Members only see bugs they reported or bugs assigned to them
        bugs = project.bug_reports.filter(
            Q(reported_by=request.user) | Q(assignees=request.user),
            is_in_trash=False
        ).distinct()

    # Determine view type for file category resources tree
    resource_view = request.GET.get("resource_view", "tree")
    if resource_view == "grid":
        resource_view = "tree"
    repo_cat_id = request.GET.get("repo_cat_id")
    current_repo_cat = None
    # If category directory ID is specified, query it
    if repo_cat_id:
        from files.models import FileCategory

        current_repo_cat = get_object_or_404(
            FileCategory, pk=repo_cat_id, project=project
        )

    from files.models import FileCategory, FileComment
    from files.forms import FileCommentForm

    active_resource_cat = current_repo_cat
    # Default to the root "resources" folder if no category is currently selected
    if not active_resource_cat:
        active_resource_cat = FileCategory.objects.filter(project=project, name="resources").first()

    # Initialize file comment form
    resource_comment_form = FileCommentForm(prefix="res_comm")
    # Process comment submissions posted to project resources tab
    if request.method == "POST" and "submit_resource_comment" in request.POST:
        resource_comment_form = FileCommentForm(request.POST, prefix="res_comm")
        if resource_comment_form.is_valid() and active_resource_cat:
            c = resource_comment_form.save(commit=False)
            c.category = active_resource_cat
            c.author = request.user
            c.save()
            messages.success(request, "Comment added to resource folder.")
            # Build redirects with appropriate query parameters preserved
            redirect_url = reverse("tasks:project_detail", kwargs={"pk": project.pk}) + "?view=resources"
            if repo_cat_id:
                redirect_url += f"&resource_view={resource_view}&repo_cat_id={repo_cat_id}"
            else:
                redirect_url += f"&resource_view={resource_view}"
            return redirect(redirect_url)

    # Query comments belonging to the active folder category
    resource_comments = []
    if active_resource_cat:
        resource_comments = active_resource_cat.comments.select_related("author").all()

    # Calculate and compile Test Case statistics metrics
    test_cases = project.test_cases.filter(is_in_trash=False)
    tc_total = test_cases.count()
    tc_passed = test_cases.filter(status="passed").count()
    tc_failed = test_cases.filter(status="failed").count()
    tc_pending = test_cases.filter(status="pending").count()
    tc_retest = test_cases.filter(status="retest").count()
    # Compute passing percentage, protecting against division-by-zero
    tc_percentage = int((tc_passed / tc_total * 100)) if tc_total > 0 else 0

    # Fetch project requirement sheets that are not trashed
    requirements = project.requirements.filter(is_in_trash=False)

    return render(
        request,
        "projects/project_detail.html",
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
            # Permissions context flags
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
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    # Cache old members list to compare changes and send notifications afterwards
    old_members = set(project.members.values_list("pk", flat=True))
    # Instantiate edit form passing current project instance and request user for scoping
    form = ProjectEditForm(request.POST or None, instance=project, user=request.user)

    if request.method == "POST" and form.is_valid():
        # Save modifications to the DB
        project = form.save()
        # Cache new member configuration
        new_members = set(project.members.values_list("pk", flat=True))
        # Determine the set of newly added users by subtracting old list from new list
        added_pks = new_members - old_members

        from ..services.notification_service import NotificationService

        # Iterate and send notifications to all newly added members
        for member in User.objects.filter(pk__in=added_pks):
            NotificationService.create_notification(
                member,
                request.user,
                "project_update",
                f"You were added to project: {project.name}",
                f'{request.user.display_name} added you as a member of "{project.name}".',
                project=project,
            )
        # Display success message
        messages.success(request, f'Project "{project.name}" updated.')
        # Redirect back to project details
        return redirect("tasks:project_detail", pk=project.pk)

    return render(
        request,
        "projects/project_edit.html",
        {
            "form": form,
            "title": f"Edit Project — {project.name}",
            "project": project,
        },
    )


@login_required
def project_settings(request, pk):
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    # Check settings permissions: Admins, PMs, Project Managers or the Project Incharge can access settings
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

    # Handle settings configuration form submission
    if request.method == "POST":
        form = ProjectSettingsForm(
            request.POST, request.FILES, instance=project, user=request.user
        )
        if form.is_valid():
            try:
                # Save changes
                project = form.save()
                messages.success(request, f'Project settings for "{project.name}" updated successfully.')
                return redirect("tasks:project_settings", pk=project.pk)
            except Exception as e:
                # Handle unexpected database save errors gracefully
                messages.error(request, f"System error saving settings: {str(e)}")
        else:
            # Map form validation errors to request messages framework to guide user correction
            if not form.errors:
                messages.error(request, "The form is invalid but no specific field errors were reported. Please check all fields.")
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = field.replace('_', ' ').capitalize()
                    messages.error(request, f"{field_name}: {error}")
    else:
        # If GET, initialize settings form populated with current model properties
        form = ProjectSettingsForm(instance=project, user=request.user)

    return render(
        request,
        "projects/project_settings.html",
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
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)
    # Fetch active system users ordered alphabetically to choose from
    all_users = User.objects.filter(is_active=True).order_by("first_name", "username")
    current_member_ids = set(project.members.values_list("pk", flat=True))

    # Process member operations (Add / Remove)
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        if action and user_id:
            target = get_object_or_404(User, pk=user_id)
            # Add user as a member
            if action == "add":
                project.members.add(target)
                from ..services.notification_service import NotificationService

                # Dispatch notification about new project assignment
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
            # Remove user from members list
            elif action == "remove":
                # Safety constraint: Do not allow removing project manager from members list
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
        "projects/project_members.html",
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

    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        # Delete actions require multi-phase confirmations for safety
        action = request.POST.get("action", "request_deletion")

        # Handle requesting or cancelling deletion requests
        if action in ["request_deletion", "cancel_deletion"]:
            msg = ProjectService.handle_deletion_request(project, request.user, action)
            if msg:
                messages.info(request, msg)

        # Handle approving a pending deletion request (requires cross-approval from another manager role)
        elif action == "approve_deletion":
            if (request.user.is_admin and project.deletion_requested_by_pm) or (
                request.user.is_project_manager
                and project.managers.filter(pk=request.user.pk).exists()
                and project.deletion_requested_by_admin
            ):
                project.delete()
                messages.success(request, f'Project "{project.name}" fully deleted.')
                return redirect("tasks:project_list")

        # Handle bypass/force delete: admins can bypass and force delete after 30 days of initial request
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

    # Assess if admin has waited long enough to force delete the project
    can_force_delete = False
    if (
        request.user.is_admin
        and project.deletion_requested_by_admin
        and project.deletion_requested_at
    ):
        if timezone.now() > project.deletion_requested_at + timedelta(days=30):
            can_force_delete = True

    pending_request = project.deletion_requests.filter(status='pending').first()

    return render(
        request,
        "projects/confirm_delete.html",
        {
            "obj": project,
            "obj_type": "Project",
            "can_force_delete": can_force_delete,
            "pending_request": pending_request,
        },
    )


@login_required
@manager_or_admin_required
def project_archive_toggle(request, pk):
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)
    # Double check manager permissions to prevent malicious attempts
    if not project.is_manager(request.user):
        messages.error(request, "Permission denied.")
        return redirect("tasks:project_detail", pk=pk)

    # Toggle the is_archived boolean field
    project.is_archived = not project.is_archived
    if project.is_archived:
        # If archiving, force status value to archived
        project.status = "archived"
    else:
        # If unarchiving, reset status to active
        if project.status == "archived":
            project.status = "active"
    
    # Save database updates
    project.save()
    # Construct feedback status text
    action_str = "archived" if project.is_archived else "unarchived"
    messages.success(request, f'Project "{project.name}" has been {action_str}.')
    
    # Redirect back to appropriate listing or detail pages
    if project.is_archived:
        return redirect("tasks:project_list")
    return redirect("tasks:project_detail", pk=pk)


@login_required
def project_task_list(request, pk):
    """Dedicated task list page for a specific project."""
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    # Secure page: restrict access to admins, members, managers, or incharge users
    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    # Extract dynamic filters from URL query parameters
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "")

    # Query tasks scoped inside visible rules, excluding bugs (which go to separate bug tracking tab)
    tasks = (
        get_visible_tasks_qs(request.user, project.tasks.exclude(task_type="bug"))
        .select_related("created_by")
        .prefetch_related("assignees")
    )

    # Apply filter parameters dynamically
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if type_filter:
        tasks = tasks.filter(task_type=type_filter)
    # Apply containment search matching title or description fields
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    # Paginate tasks showing 20 records per page
    paginator = Paginator(tasks.order_by("-updated_at"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Determine manager role status for template action controls
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
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    # Secure page: restrict access to authenticated members, managers, or incharge users
    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    # Extract dynamic filters from query parameters
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "")

    # Query requirements belonging to the project that are active (not in trash)
    requirements = project.requirements.filter(is_in_trash=False)

    # Filter requirements dynamically
    if status_filter:
        requirements = requirements.filter(status=status_filter)
    if priority_filter:
        requirements = requirements.filter(priority=priority_filter)
    if type_filter:
        requirements = requirements.filter(requirement_type=type_filter)
    # Apply containment search on requirement names or description texts
    if search:
        requirements = requirements.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    # Paginate requirements showing 20 records per page
    paginator = Paginator(requirements.order_by("-created_at"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Determine manager role status for template action controls
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
    # Retrieve project or return 404
    project = get_object_or_404(Project, pk=pk)

    # Secure page: restrict access to authenticated members, managers, or incharge users
    if not (
        request.user.is_admin
        or project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    ):
        messages.error(request, "You do not have access to this project.")
        return redirect("tasks:project_list")

    # Extract dynamic filters from query parameters
    status_filter = request.GET.get("status", "")
    severity_filter = request.GET.get("severity", "")
    search = request.GET.get("q", "")

    # Check manager role status to apply appropriate visibility boundaries
    is_pm = (
        project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
        or request.user.is_project_manager
    )

    # Scope queryset: PMs see all active bugs; normal members see only reported/assigned bugs
    if is_pm:
        bugs = project.bug_reports.filter(is_in_trash=False)
    else:
        bugs = project.bug_reports.filter(
            Q(reported_by=request.user) | Q(assignees=request.user),
            is_in_trash=False,
        ).distinct()

    # Filter bugs dynamically based on selections
    if status_filter:
        bugs = bugs.filter(status=status_filter)
    if severity_filter:
        bugs = bugs.filter(severity=severity_filter)
    # Apply containment search matching title or description fields
    if search:
        bugs = bugs.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    # Paginate bugs showing 20 records per page
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
