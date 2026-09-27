from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Project, BugReport, Task, Notification
from ..forms import BugReportForm
from ..services.notification_service import NotificationService


@login_required
def bug_list(request):
    severity_filter = request.GET.get("severity", "")
    status_filter = request.GET.get("status", "")
    project_filter = request.GET.get("project", "")
    assigned_only = request.GET.get("assigned_to_me", "")

    if request.user.is_admin or request.user.is_project_manager:
        bugs = BugReport.objects.filter(is_in_trash=False)
    else:
        bugs = BugReport.objects.filter(
            Q(project__members=request.user)
            | Q(project__managers=request.user)
            | Q(reported_by=request.user)
            | Q(assignees=request.user),
            is_in_trash=False
        ).distinct()

    if assigned_only:
        bugs = bugs.filter(assignees=request.user)
    if severity_filter:
        bugs = bugs.filter(severity=severity_filter)
    if status_filter:
        bugs = bugs.filter(status=status_filter)
    if project_filter:
        bugs = bugs.filter(project_id=project_filter)

    if request.user.is_admin or request.user.is_project_manager:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(managers=request.user) | Q(members=request.user)
        ).distinct()

    current_project = None
    if project_filter:
        current_project = Project.objects.filter(id=project_filter).first()

    return render(
        request,
        "bugs/bug_list.html",  # Updated path
        {
            "bugs": bugs.select_related("project", "reported_by")
            .prefetch_related("assignees")
            .order_by("-created_at"),
            "severity_choices": BugReport.SEVERITY_CHOICES,
            "status_choices": BugReport.STATUS_CHOICES,
            "projects": projects,
            "severity_filter": severity_filter,
            "status_filter": status_filter,
            "project_filter": project_filter,
            "assigned_only": assigned_only,
            "project": current_project,
            "is_pm": request.user.is_admin or request.user.is_project_manager or (current_project and current_project.managers.filter(pk=request.user.pk).exists()),
            "is_incharge": current_project.project_incharge == request.user if current_project else False,
        },
    )


@login_required
def bug_create(request):
    project_id = request.GET.get("project")
    project = get_object_or_404(Project, pk=project_id) if project_id else None
    # Project Managers allowed

    form = BugReportForm(request.POST or None, user=request.user, project=project)
    if request.method == "POST" and form.is_valid():
        bug = form.save(commit=False)
        bug.reported_by = request.user
        bug.save()
        form.save_m2m()

        # Notify Project Managers
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
            new_task.assignees.set(bug.assignees.all())

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
        "bugs/bug_form.html",  # Updated path
        {
            "form": form, 
            "title": "Report a Bug", 
            "action": "Submit Report",
            "is_pm": request.user.is_admin or request.user.is_project_manager or (project and project.managers.filter(pk=request.user.pk).exists()),
            "is_incharge": project.project_incharge == request.user if project else False,
        },
    )


from django.utils import timezone
from ..forms import BugReportForm, BugCommentForm, BugResolutionForm
from ..models import Project, BugReport, Task, BugComment

@login_required
def bug_detail(request, pk):
    bug = get_object_or_404(BugReport, pk=pk)

    # Mark bug-related notifications as read
    if bug.linked_task:
        Notification.objects.filter(recipient=request.user, task=bug.linked_task, is_read=False).update(is_read=True)
    else:
        # Fallback to project-level notifications if no task linked yet
        Notification.objects.filter(recipient=request.user, project=bug.project, notification_type="bug_reported", is_read=False).update(is_read=True)

    project = bug.project
    comments = bug.comments.all().select_related("author")
    
    is_pm = request.user.is_admin or request.user.is_project_manager or project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    is_assignee = bug.assignees.filter(pk=request.user.pk).exists()

    comment_form = BugCommentForm()
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
    bug = get_object_or_404(BugReport, pk=pk)
    if request.method == "POST":
        form = BugCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.bug = bug
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Error adding comment.")
    return redirect("tasks:bug_detail", pk=pk)

@login_required
def bug_resolve(request, pk):
    bug = get_object_or_404(BugReport, pk=pk)
    project = bug.project
    
    is_pm = request.user.is_admin or request.user.is_project_manager or project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    is_assignee = bug.assignees.filter(pk=request.user.pk).exists()

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
            
            # If linked to a task, maybe update task status too?
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
    bug = get_object_or_404(BugReport, pk=pk)
    # Project Managers allowed

    if not (request.user.is_admin or request.user in bug.project.managers.all() or request.user == bug.project.project_incharge or request.user == bug.reported_by):
        messages.error(request, "You do not have permission to edit this bug report.")
        return redirect("tasks:bug_detail", pk=pk)

    old_assignees = set(bug.assignees.all())
    form = BugReportForm(request.POST or None, instance=bug, user=request.user)
    if request.method == "POST" and form.is_valid():
        bug = form.save()
        new_assignees = set(bug.assignees.all())
        added_assignees = new_assignees - old_assignees

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
        "bugs/bug_form.html",  # Updated path
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
    bug = get_object_or_404(BugReport, pk=pk)
    project = bug.project
    
    if not (request.user.is_admin or request.user in project.managers.all() or request.user == project.project_incharge or request.user == bug.reported_by):
        messages.error(request, "You do not have permission to delete this bug report.")
        return redirect("tasks:bug_detail", pk=pk)

    bug.is_in_trash = True
    bug.deleted_at = timezone.now()
    bug.deleted_by = request.user
    bug.save()

    if bug.linked_task:
        bug.linked_task.is_in_trash = True
        bug.linked_task.deleted_at = timezone.now()
        bug.linked_task.deleted_by = request.user
        bug.linked_task.save()
    
    messages.success(request, f'Bug "{bug.title}" moved to trash.')
    return redirect("tasks:project_detail", pk=project.pk)
