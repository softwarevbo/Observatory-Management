from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tasks.models import Project, Task
from tasks.services.notification_service import NotificationService
from notifications.models import Notification
from .models import BugReport, BugComment
from .forms import BugReportForm, BugCommentForm, BugResolutionForm

"""
This module contains the View controller actions for the Bug Tracking system.
It utilizes function-based views decorated with `@login_required` to restrict access.

Access control is enforced on all endpoints to prevent users from editing, viewing,
commenting on, or resolving bugs in projects they do not participate in.
"""

@login_required
def bug_list(request):
    """
    Renders a paginated, search-enabled, and filterable list of bug reports.
    
    Access Control:
    - Admins and Project Managers can view all untrashed bugs in the system.
    - Regular members can only view bugs belonging to projects they manage or participate in,
      or bugs they reported themselves, or bugs they are explicitly assigned to.
    """
    # Extract query params for filtering
    severity_filter = request.GET.get("severity", "")
    status_filter = request.GET.get("status", "")
    project_filter = request.GET.get("project", "")
    assigned_only = request.GET.get("assigned_to_me", "")

    # 1. Fetch initial queryset based on roles
    if request.user.is_admin or request.user.is_project_manager:
        bugs = BugReport.objects.filter(is_in_trash=False)
    else:
        # Use Q objects to query bugs where user is linked in projects, reporter, or assignee list
        bugs = BugReport.objects.filter(
            Q(project__managers=request.user)
            | Q(project__project_incharge=request.user)
            | Q(reported_by=request.user)
            | Q(assignees=request.user),
            is_in_trash=False
        ).distinct()

    # 2. Apply query filters
    if assigned_only:
        bugs = bugs.filter(assignees=request.user)
    if severity_filter:
        bugs = bugs.filter(severity=severity_filter)
    if status_filter:
        bugs = bugs.filter(status=status_filter)
    if project_filter:
        bugs = bugs.filter(project_id=project_filter)

    # 3. Retrieve list of project choices for the filter dropdown list
    if request.user.is_admin or request.user.is_project_manager:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(managers=request.user) | Q(members=request.user)
        ).distinct()

    current_project = None
    if project_filter:
        current_project = Project.objects.filter(id=project_filter).first()

    # 4. Perform pagination
    from django.core.paginator import Paginator
    # Use select_related and prefetch_related to load relationships and avoid database N+1 query overheads
    bugs_qs = (
        bugs.select_related("project", "reported_by")
        .prefetch_related("assignees")
        .order_by("-created_at")
    )
    paginator = Paginator(bugs_qs, 10) # 10 records per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "bugs/bug_list.html",
        {
            "bugs": page_obj.object_list,
            "page_obj": page_obj,
            "severity_choices": BugReport.SEVERITY_CHOICES,
            "status_choices": BugReport.STATUS_CHOICES,
            "projects": projects,
            "severity_filter": severity_filter,
            "status_filter": status_filter,
            "project_filter": project_filter,
            "assigned_only": assigned_only,
            "project": current_project,
            # Helper properties mapping user role permissions in current template
            "is_pm": request.user.is_admin or request.user.is_project_manager or (current_project and current_project.managers.filter(pk=request.user.pk).exists()),
            "is_incharge": current_project.project_incharge == request.user if current_project else False,
        },
    )


@login_required
def bug_create(request):
    """
    Renders and processes bug creation forms.
    On successful report:
    - Notifies Project Managers of the new bug report.
    - If assignees are set, creates a companion 'bug'-type PM Task, links it, and notifies assignees.
    """
    project_id = request.GET.get("project")
    project = get_object_or_404(Project, pk=project_id) if project_id else None

    form = BugReportForm(request.POST or None, user=request.user, project=project)
    
    if request.method == "POST" and form.is_valid():
        bug = form.save(commit=False)
        bug.reported_by = request.user
        bug.save()
        # Save many-to-many fields (assignees)
        form.save_m2m()

        # 1. Notify Project Managers
        project = bug.project
        if project:
            for manager in project.managers.all():
                if manager != request.user:
                    NotificationService.create_notification(
                        manager,
                        request.user,
                        "bug_reported",
                        f"New Bug Reported: {bug.title}",
                        f'{request.user.display_name} reported a new bug in "{project.name}": {bug.title}',
                        project=project,
                    )

        # 2. If assignees are chosen immediately, spawn a companion tracking Task
        if bug.assignees.exists():
            new_task = Task.objects.create(
                title=f"[Bug] {bug.title}",
                description=bug.description,
                project=bug.project,
                task_type="bug",
                status="todo",
                priority=bug.severity,
                created_by=request.user,
            )
            # Copy assignees list
            new_task.assignees.set(bug.assignees.all())
            bug.linked_task = new_task
            bug.save()

        # 3. Notify Assignees
        for assignee in bug.assignees.all():
            if assignee != request.user:
                NotificationService.create_notification(
                    assignee,
                    request.user,
                    "task_assigned",
                    f"Bug assigned to you: {bug.title}",
                    f'{request.user.display_name} assigned you a bug report in "{bug.project.name}": {bug.title}.',
                    project=bug.project,
                )
        messages.success(request, f'Bug "{bug.title}" reported.')
        return redirect("tasks:bug_detail", pk=bug.pk)

    return render(
        request,
        "bugs/bug_form.html",
        {
            "form": form,
            "title": "Report a Bug",
            "action": "Submit Report",
            "is_pm": request.user.is_admin or request.user.is_project_manager or (project and project.managers.filter(pk=request.user.pk).exists()),
            "is_incharge": project.project_incharge == request.user if project else False,
        },
    )


@login_required
def bug_detail(request, pk):
    """
    Renders details of a bug report.
    - Sets related unread notifications to 'Read' status.
    - Loads threaded comments and attachment forms.
    - Sets up resolution forms for authorized developers.
    """
    bug = get_object_or_404(BugReport, pk=pk)

    # Admins/PMs check on trashed items
    if bug.is_in_trash and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "This bug report is in the trash and can only be viewed by Admins or Project Managers.")
        return redirect("tasks:project_detail", pk=bug.project.pk)

    project = bug.project
    is_pm = request.user.is_admin or request.user.is_project_manager or (project and project.managers.filter(pk=request.user.pk).exists())
    is_incharge = project.project_incharge == request.user if project else False
    is_assignee = bug.assignees.filter(pk=request.user.pk).exists()
    is_reporter = bug.reported_by == request.user

    # Security access check
    if not (is_pm or is_incharge or is_assignee or is_reporter):
        messages.error(request, "You do not have permission to view this bug report.")
        return redirect("tasks:project_list")

    # Mark corresponding notifications as read
    if bug.linked_task:
        Notification.objects.filter(recipient=request.user, task=bug.linked_task, is_read=False).update(is_read=True)
    else:
        Notification.objects.filter(recipient=request.user, project=project, notification_type="bug_reported", is_read=False).update(is_read=True)

    # Retrieve only root comments (comments where parent is null). Replies are loaded via related-name queries in templates.
    comments = bug.comments.filter(parent__isnull=True).select_related("author")
    
    # Initialize forms
    comment_form = BugCommentForm()
    
    # Only assignees or project managers can resolve/close bugs
    resolution_form = BugResolutionForm(instance=bug, is_leadership=(is_pm or is_incharge)) if (is_pm or is_incharge or is_assignee) else None

    return render(
        request,
        "bugs/bug_detail.html",
        {
            "bug": bug,
            "comments": comments,
            "comment_form": comment_form,
            "resolution_form": resolution_form,
            "is_pm": is_pm,
            "is_incharge": is_incharge,
            "is_assignee": is_assignee,
        }
    )


@login_required
def bug_comment_add(request, pk):
    """
    Saves a text comment or threaded reply on a bug report.
    """
    bug = get_object_or_404(BugReport, pk=pk)
    project = bug.project
    is_pm = request.user.is_admin or request.user.is_project_manager or (project and project.managers.filter(pk=request.user.pk).exists())
    is_incharge = project.project_incharge == request.user if project else False
    is_assignee = bug.assignees.filter(pk=request.user.pk).exists()
    is_reporter = bug.reported_by == request.user

    # Access validation
    if not (is_pm or is_incharge or is_assignee or is_reporter):
        messages.error(request, "You do not have permission to comment on this bug report.")
        return redirect("tasks:project_list")

    if request.method == "POST":
        form = BugCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.bug = bug
            comment.author = request.user
            
            # If parent_id is sent in request, it's a nested reply. Link it.
            parent_id = request.POST.get("parent_id")
            if parent_id:
                try:
                    comment.parent = BugComment.objects.get(pk=parent_id)
                except BugComment.DoesNotExist:
                    pass
            comment.save()
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Error adding comment.")
    return redirect("tasks:bug_detail", pk=pk)


@login_required
def bug_resolve(request, pk):
    """
    Updates bug report resolution details and status choices.
    If bug state is updated to 'resolved' or 'closed', synchronizes the companion linked task state to 'done'.
    """
    bug = get_object_or_404(BugReport, pk=pk)
    project = bug.project
    
    if bug.is_in_trash:
        messages.error(request, "Cannot resolve a bug report that is in the trash.")
        return redirect("tasks:project_detail", pk=project.pk)
        
    is_pm = request.user.is_admin or request.user.is_project_manager or project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    is_assignee = bug.assignees.filter(pk=request.user.pk).exists()

    # Access check: only developers assigned, or leadership, can log resolutions
    if not (is_pm or is_incharge or is_assignee):
        messages.error(request, "You do not have permission to resolve this bug.")
        return redirect("tasks:bug_detail", pk=pk)

    if request.method == "POST":
        form = BugResolutionForm(request.POST, request.FILES, instance=bug, is_leadership=(is_pm or is_incharge))
        if form.is_valid():
            bug = form.save(commit=False)
            bug.resolved_by = request.user
            bug.resolution_date = timezone.now()
            bug.save()
            
            # Synchronize companion task status
            if bug.linked_task and bug.status in ["resolved", "closed"]:
                task = bug.linked_task
                task.status = "done"
                task.save()
                
            messages.success(request, f"Bug status updated to {bug.get_status_display()}.")
        else:
            messages.error(request, "Error updating bug status.")
    return redirect("tasks:bug_detail", pk=pk)


@login_required
def bug_edit(request, pk):
    """
    Edits an existing bug report.
    If new assignees are added, spaws another companion Task and sends alerts to newly assigned users.
    """
    bug = get_object_or_404(BugReport, pk=pk)

    if bug.is_in_trash:
        messages.error(request, "Cannot edit a bug report that is in the trash.")
        return redirect("tasks:project_detail", pk=bug.project.pk)

    # Permission check: reporter, managers, or project incharge only
    if not (request.user.is_admin or request.user in bug.project.managers.all() or request.user == bug.project.project_incharge or request.user == bug.reported_by):
        messages.error(request, "You do not have permission to edit this bug report.")
        return redirect("tasks:bug_detail", pk=pk)

    # Trace old assignees before saving form updates
    old_assignees = set(bug.assignees.all())
    form = BugReportForm(request.POST or None, instance=bug, user=request.user)
    
    if request.method == "POST" and form.is_valid():
        bug = form.save()
        new_assignees = set(bug.assignees.all())
        
        # Calculate added assignees difference
        added_assignees = new_assignees - old_assignees

        # If new developers are added, create another companion Task tracking the bug for them
        if added_assignees:
            new_task = Task.objects.create(
                title=f"[Bug] {bug.title}",
                description=bug.description,
                project=bug.project,
                task_type="bug",
                status="todo",
                priority=bug.severity,
                created_by=request.user,
            )
            new_task.assignees.set(added_assignees)

        # Send notifications
        for assignee in added_assignees:
            if assignee != request.user:
                NotificationService.create_notification(
                    assignee,
                    request.user,
                    "task_assigned",
                    f"Bug assigned to you: {bug.title}",
                    f'{request.user.display_name} assigned you a bug report in "{bug.project.name}": {bug.title}.',
                    project=bug.project,
                )
        messages.success(request, "Bug report updated.")
        return redirect("tasks:bug_detail", pk=pk)

    return render(
        request,
        "bugs/bug_form.html",
        {
            "form": form,
            "title": "Edit Bug Report",
            "action": "Save Changes",
            "bug": bug,
            "is_pm": request.user.is_admin or request.user.is_project_manager or bug.project.managers.filter(pk=request.user.pk).exists(),
            "is_incharge": bug.project.project_incharge == request.user,
        },
    )


@login_required
def bug_delete(request, pk):
    """
    Soft-deletes a bug report by moving it to the trash (`is_in_trash=True`).
    Automatically soft-deletes the companion task as well.
    """
    bug = get_object_or_404(BugReport, pk=pk)
    project = bug.project

    if bug.is_in_trash:
        messages.error(request, "This bug report is already in the trash.")
        return redirect("tasks:project_detail", pk=project.pk)
    
    # Permission check: reporter, managers, or project incharge only
    if not (request.user.is_admin or request.user in project.managers.all() or request.user == project.project_incharge or request.user == bug.reported_by):
        messages.error(request, "You do not have permission to delete this bug report.")
        return redirect("tasks:bug_detail", pk=pk)

    # Soft delete bug report
    bug.is_in_trash = True
    bug.deleted_at = timezone.now()
    bug.deleted_by = request.user
    bug.save()

    # Soft delete companion task
    if bug.linked_task:
        bug.linked_task.is_in_trash = True
        bug.linked_task.deleted_at = timezone.now()
        bug.linked_task.deleted_by = request.user
        bug.linked_task.save()
    
    messages.success(request, f'Bug "{bug.title}" moved to trash.')
    return redirect("tasks:project_detail", pk=project.pk)
