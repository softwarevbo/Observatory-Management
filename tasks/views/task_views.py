from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
import json

from django.forms import modelformset_factory
from django.urls import reverse
from ..models import Project, Task, ProjectModule, Comment
from notifications.models import Notification
from ..forms import TaskForm, CommentForm, BulkTaskForm
from ..decorators import manager_or_admin_required
from ..utils.query_utils import get_visible_tasks_qs
from ..services.notification_service import NotificationService


@login_required
def task_bulk_create(request, pk):
    """
    Renders a dynamic formset grid permitting project members to batch-create tasks.
    Non-privileged creators trigger an approval workflow where the tasks remain unapproved.
    """
    # Retrieve project context
    project = get_object_or_404(Project, pk=pk)
    is_pm = project.managers.filter(pk=request.user.pk).exists()
    is_assignee = project.tasks.filter(assignees=request.user).exists()

    # Define modelformset factory scope
    TaskFormSet = modelformset_factory(
        Task,
        form=BulkTaskForm,
        extra=1,
        can_delete=True,
    )

    if request.method == "POST":
        formset = TaskFormSet(
            request.POST,
            queryset=Task.objects.none(),
            form_kwargs={"project": project, "user": request.user},
        )
        if formset.is_valid():
            saved_count = 0
            for form in formset:
                # Iterate and skip blank rows or elements marked for deletion
                if form.cleaned_data.get("title") and not form.cleaned_data.get("DELETE"):
                    instance = form.save(commit=False)
                    instance.project = project
                    instance.created_by = request.user
                    
                    # Tasks require approval if created by standard project contributors
                    is_privileged = project.is_manager(request.user) or project.is_incharge(request.user)
                    instance.is_approved = is_privileged
                    instance.save()
                    form.save_m2m()  # Save assignees and other many-to-many associations
                    saved_count += 1
            
            messages.success(request, f"{saved_count} tasks created successfully.")
            return redirect(reverse("tasks:project_detail", args=[project.pk]))
        else:
            # Aggregate validation failure alerts across the formset
            error_msgs = []
            for i, form_errors in enumerate(formset.errors):
                if form_errors:
                    error_msgs.append(f"Row {i+1}: {', '.join([f'{k}: {v[0]}' for k, v in form_errors.items()])}")
            
            messages.warning(request, "Please correct the errors in the grid below.")
            if error_msgs:
                for err in error_msgs[:5]: # Show top 5 errors to avoid view flooding
                    messages.error(request, err)
    else:
        formset = TaskFormSet(
            queryset=Task.objects.none(),
            form_kwargs={"project": project, "user": request.user},
        )
        # Pre-populate project parameters and hide the project field widget
        for form in formset:
            if "project" in form.fields:
                form.fields["project"].initial = project
                from django import forms
                form.fields["project"].widget = forms.HiddenInput()

    return render(
        request,
        "tasks/task_bulk_form.html",
        {"formset": formset, "project": project, "title": "Bulk Add Tasks"},
    )


@login_required
def get_project_data(request):
    """
    AJAX view to fetch project-specific data (modules, approved requirements, members, tasks)
    to populate dynamic drop-down selections in bulk task creations.
    """
    from django.http import JsonResponse
    project_id = request.GET.get("project_id")
    if not project_id:
        return JsonResponse({"error": "No project ID provided"}, status=400)
    
    project = get_object_or_404(Project, pk=project_id)
    
    modules = list(project.modules.all().values("id", "name"))
    requirements = list(project.requirements.filter(is_approved=True, is_in_trash=False).values("id", "name", "req_id").order_by("req_id"))
    
    # Get members and managers associated with the resolved project
    member_ids = list(project.members.values_list("pk", flat=True))
    member_ids.extend(project.managers.values_list("pk", flat=True))
    from django.contrib.auth import get_user_model
    User = get_user_model()
    members = list(User.objects.filter(pk__in=member_ids, is_active=True).values("id", "first_name", "last_name", "username"))
    
    # Format user display names cleanly
    for m in members:
        m["display_name"] = f"{m['first_name']} {m['last_name']}" if m["first_name"] else m["username"]

    tasks = list(project.tasks.filter(is_in_trash=False).exclude(linked_bugs__is_in_trash=True).values("id", "title", "task_id"))

    return JsonResponse({
        "modules": modules,
        "requirements": requirements,
        "members": members,
        "tasks": tasks
    })


@login_required
def task_list(request):
    """
    List view displaying all active tasks with support for searching, multi-criteria filtering, and pagination.
    """
    user = request.user
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    search = request.GET.get("q", "")
    my_only = request.GET.get("mine", "")
    project_filter = request.GET.get("project", "")
    overdue_filter = request.GET.get("overdue", "")
    sort = request.GET.get("sort", "-updated_at")

    # Define whitelist of allowable sort fields to block SQL injections
    allowed_sort_fields = [
        "title",
        "project__name",
        "task_type",
        "priority",
        "status",
        "due_date",
        "updated_at",
        "--updated_at",
        "-updated_at",
        "-title",
        "-project__name",
        "-task_type",
        "-priority",
        "-status",
        "-due_date",
    ]
    if sort not in allowed_sort_fields:
        sort = "-updated_at"

    # Enforce role logic: generic administrators do not manage task logs directly
    if user.is_admin:
        messages.error(request, "Admins do not have access to tasks.")
        return redirect("tasks:dashboard")

    # Retrieve tasks where user is assigned or belongs to the project membership
    tasks = get_visible_tasks_qs(
        user,
        Task.objects.filter(
            Q(project__members=user) | Q(project__managers=user) | Q(assignees=user),
            is_in_trash=False
        ).distinct(),
    )

    # Apply filters dynamically based on user requests
    if my_only:
        tasks = tasks.filter(assignees=user)
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if project_filter:
        tasks = tasks.filter(project_id=project_filter)
    if overdue_filter:
        from django.utils import timezone
        # Fetch items past due date that are not completed
        tasks = tasks.filter(due_date__lt=timezone.now().date()).exclude(status="done")
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    # Fetch projects the user has access to
    if user.is_admin:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(Q(managers=user) | Q(members=user)).distinct()

    task_qs = (
        tasks.select_related("project").prefetch_related("assignees").order_by(sort)
    )

    if my_only and sort == "-updated_at":
        task_qs = task_qs.order_by("project", "-updated_at")

    # Paginate results list
    paginator = Paginator(task_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    current_project = None
    if project_filter:
        current_project = Project.objects.filter(id=project_filter).first()

    return render(
        request,
        "tasks/task_list.html",
        {
            "tasks": page_obj,
            "page_obj": page_obj,
            "status_choices": Task.STATUS_CHOICES,
            "priority_choices": Task.PRIORITY_CHOICES,
            "projects": projects,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "project_filter": project_filter,
            "search": search,
            "my_only": my_only,
            "my_tasks": my_only,
            "current_sort": sort,
            "overdue_filter": overdue_filter,
            "project": current_project,
        },
    )


@login_required
def task_create(request):
    project_id = request.GET.get("project")
    module_id = request.GET.get("module")
    project = get_object_or_404(Project, pk=project_id) if project_id else None

    # Pre-populate specific module if context provided in GET request
    initial = {}
    if module_id:
        initial["module"] = get_object_or_404(ProjectModule, pk=module_id)

    form = TaskForm(
        request.POST or None, user=request.user, project=project, initial=initial
    )

    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        
        # Verify approval privileges: managers/admins create approved tasks, others require sign-off
        is_privileged = (project.is_manager(request.user) or project.is_incharge(request.user)) if project else (request.user.is_admin or request.user.is_project_manager)
        task.is_approved = is_privileged
        task.save()
        form.save_m2m()
        
        # Dispatch task assignment alerts to assigned users
        for assignee in task.assignees.all():
            if assignee != request.user:
                NotificationService.create_notification(
                    assignee,
                    request.user,
                    "task_assigned",
                    f"New task assigned: {task.title}",
                    f'{request.user.display_name} assigned you a task in "{task.project.name}".',
                    task=task,
                    project=task.project,
                )
        messages.success(request, f'Task "{task.title}" created.')
        return redirect("tasks:task_detail", pk=task.pk)
    elif request.method == "POST":
        messages.warning(request, "Please correct the errors below.")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")

    return render(
        request,
        "tasks/task_form.html",
        {
            "form": form,
            "title": "New Task",
            "action": "Create Task",
            "project": project,
        },
    )


@login_required
def task_detail(request, pk):
    """
    Renders detailed properties of a single task, containing associated subtasks, comments, and files.
    """
    task = get_object_or_404(Task, pk=pk)

    # Mark relevant notifications for the task as read
    Notification.objects.filter(recipient=request.user, task=task, is_read=False).update(is_read=True)

    # Restrict preview of trashed items to managers/admins
    if task.is_in_trash and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "This task is in the trash and can only be previewed by Admins or Project Managers.")
        return redirect("tasks:project_detail", pk=task.project.pk)

    # Resolve roles for strict access gating
    is_pm = task.project.managers.filter(pk=request.user.pk).exists()
    is_assignee = task.assignees.filter(pk=request.user.pk).exists()
    is_incharge = task.project.project_incharge == request.user
    
    if not (request.user.is_admin or request.user.is_project_manager or is_pm or is_assignee or is_incharge):
        messages.error(request, "Access restricted: Only Project Managers, assigned members, and the project in-charge can view this task.")
        return redirect("tasks:project_detail", pk=task.project.pk)

    # Query comments hierarchy, subtasks, and files
    comments = task.comments.filter(parent__isnull=True).select_related("author").all()
    subtasks = task.subtasks.prefetch_related("assignees").all()
    comment_form = CommentForm()
    project_notes = task.project.kb_notes.all() if task.project else []
    latest_task_files = (
        task.files.filter(versions__isnull=True)
        .select_related("uploaded_by", "parent_file")
        .prefetch_related("versions")
    )

    if request.method == "POST":
        # Handle new comment submission
        comment_form = CommentForm(request.POST, request.FILES)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            parent_id = request.POST.get("parent_id")
            if parent_id:
                try:
                    comment.parent = Comment.objects.get(pk=parent_id)
                except Comment.DoesNotExist:
                    pass
            comment.save()

            # Identify stakeholders to notify
            users_to_notify = set(task.assignees.all())
            if task.created_by:
                users_to_notify.add(task.created_by)
            if task.project:
                users_to_notify.update(task.project.managers.all())

            # Dispatch notification alerts
            for user_to_notify in users_to_notify:
                if user_to_notify != request.user:
                    NotificationService.create_notification(
                        user_to_notify,
                        request.user,
                        "comment_added",
                        f"New comment on: {task.title}",
                        f"{request.user.display_name} commented on a task you're involved in.",
                        task=task,
                        project=task.project,
                    )
            messages.success(request, "Comment posted.")
            return redirect("tasks:task_detail", pk=pk)

    related_bugs = task.linked_bugs.all()

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "comments": comments,
            "subtasks": subtasks,
            "related_bugs": related_bugs,
            "comment_form": comment_form,
            "project_notes": project_notes,
            "latest_task_files": latest_task_files,
            "is_pm": is_pm,
            "is_assignee": is_assignee,
            "is_author": task.created_by == request.user,
        },
    )


def task_edit(request, pk):
    """
    Renders editing interfaces for an existing task with role validations.
    """
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    
    is_pm = task.project.managers.filter(pk=request.user.pk).exists()
    is_assignee = task.assignees.filter(pk=request.user.pk).exists()
    is_incharge = task.project.project_incharge == request.user
    
    is_member = (
        project.members.filter(pk=request.user.pk).exists()
        or is_pm
        or is_incharge
        or request.user.is_admin
    )
    
    # Verify editor permissions (must be admin, pm, incharge or task author)
    if not (request.user.is_admin or is_pm or is_incharge or task.created_by == request.user):
        messages.error(request, "You do not have permission to edit this task.")
        return redirect("tasks:task_detail", pk=pk)

    old_assignees = set(task.assignees.all())
    old_status = task.status
    form = TaskForm(
        request.POST or None, instance=task, user=request.user, project=task.project
    )
    if request.method == "POST" and form.is_valid():
        new_status = form.cleaned_data.get("status")
        
        # Enforce that only PMs/admins/incharges can transition tasks to the 'done' state
        if new_status == "done":
            if not is_pm and not request.user.is_admin and not is_incharge:
                messages.error(
                    request,
                    "Only Project Managers or the Project In-charge can mark a task as 'Done'. Please submit 'In Review' instead.",
                )
                return redirect("tasks:task_edit", pk=task.pk)
            
            # Tasks cannot be completed unless linked test cases are successfully passed
            if not task.can_complete:
                messages.error(
                    request,
                    "A task cannot be marked as completed unless all linked test cases are passed.",
                )
                return redirect("tasks:task_edit", pk=task.pk)

        task = form.save()

        # Alert PMs if all release tasks are completed
        if task.status == "done" and old_status != "done" and task.release:
            release = task.release
            if not release.tasks.exclude(status="done").exists():
                for pm in release.project.managers.all():
                    NotificationService.create_notification(
                        pm,
                        request.user,
                        "project_update",
                        f"Release ready for approval: {release.name}",
                        f'All tasks for release "{release.name}" are completed. Please review and approve.',
                        project=release.project,
                    )

        # Notify newly added assignees
        new_assignees = set(task.assignees.all())
        added_assignees = new_assignees - old_assignees
        for assignee in added_assignees:
            if assignee != request.user:
                NotificationService.create_notification(
                    assignee,
                    request.user,
                    "task_assigned",
                    f"Task assigned to you: {task.title}",
                    f"{request.user.display_name} assigned you a task.",
                    task=task,
                    project=task.project,
                )

        # Notify stakeholders of status modifications
        if old_status != task.status:
            if is_assignee and not is_pm:
                for manager in task.project.managers.all():
                    NotificationService.create_notification(
                        manager,
                        request.user,
                        "project_update",
                        f"Task status updated: {task.title}",
                        f'{request.user.display_name} updated the status of task "{task.title}" to {task.get_status_display()}.',
                        task=task,
                        project=task.project,
                    )
            if not is_assignee or is_pm:
                for assignee in task.assignees.all():
                    if assignee != request.user:
                        NotificationService.create_notification(
                            assignee,
                            request.user,
                            "project_update",
                            f"Task status updated: {task.title}",
                            f'{request.user.display_name} updated the status of your task "{task.title}" to {task.get_status_display()}.',
                            task=task,
                            project=task.project,
                        )

        messages.success(request, f'Task "{task.title}" updated.')
        return redirect("tasks:task_detail", pk=task.pk)
    elif request.method == "POST":
        messages.warning(request, "Please correct the errors below.")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")

    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "title": "Edit Task", "action": "Save Changes", "task": task},
    )


@login_required
def task_delete(request, pk):
    """
    Flags a task as deleted (moves it to the trash folder) with validation checks.
    """
    task = get_object_or_404(Task, pk=pk)
    project = task.project

    if task.created_by != request.user and not request.user.is_admin:
        messages.error(request, "Only the creator of the task can delete it.")
        return redirect("tasks:task_detail", pk=pk)

    if request.method == "POST":
        task.is_in_trash = True
        task.deleted_at = timezone.now()
        task.deleted_by = request.user
        task.save()
        messages.success(request, "Task moved to trash.")
        return redirect("tasks:project_detail", pk=project.pk)

    return render(
        request, "projects/confirm_delete.html", {"obj": task, "obj_type": "Task"}
    )


@login_required
def task_update_status(request, pk):
    """
    AJAX endpoint to update status attributes on kanban views.
    """
    task = get_object_or_404(Task, pk=pk)
    pms = task.project.managers.all()
    is_pm = request.user in pms
    is_incharge = task.project.project_incharge == request.user

    # Restrict kanban state movements to managers and project in-charge roles
    if not (is_pm or request.user.is_admin or request.user.is_project_manager or is_incharge):
        return JsonResponse(
            {
                "success": False,
                "message": "Only Project Managers or the Project In-charge can change the task status.",
            },
            status=403,
        )

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_status = data.get("status")
            if new_status in dict(Task.STATUS_CHOICES):
                # Verify passed test cases block before marking task as done
                if new_status == "done" and not task.can_complete:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "A task cannot be marked as completed unless all linked test cases are passed.",
                        },
                        status=400,
                    )
                old_status = task.status
                task.status = new_status
                task.save()

                # Dispatch release review alerts
                if (
                    task.status in ["review", "done"]
                    and old_status not in ["review", "done"]
                    and task.release
                ):
                    release = task.release
                    if not release.tasks.exclude(
                        status__in=["review", "done"]
                    ).exists():
                        for pm in release.project.managers.all():
                            NotificationService.create_notification(
                                pm,
                                request.user,
                                "project_update",
                                f"Release ready for review & completion: {release.name}",
                                f'All tasks for release "{release.name}" are reviewed or done.',
                                project=release.project,
                            )

                # Alert assignees of progress transitions
                for assignee in task.assignees.all():
                    if assignee not in pms and assignee != request.user:
                        NotificationService.create_notification(
                            assignee,
                            request.user,
                            "task_updated",
                            f"Task status changed: {task.title}",
                            f"{request.user.display_name} moved your task to {task.get_status_display()}.",
                            task=task,
                            project=task.project,
                        )
                return JsonResponse(
                    {"success": True, "progress": task.project.progress}
                )
        except Exception:
            pass
    return JsonResponse({"success": False}, status=400)


@login_required
def task_approve(request, pk):
    """
    Approve tasks submitted by generic members.
    """
    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or task.project.is_manager(request.user)):
        messages.error(request, "Only managers can approve tasks.")
        return redirect("tasks:task_detail", pk=pk)
        
    task.is_approved = True
    task.save()
    messages.success(request, f"Task '{task.title}' has been approved.")
    return redirect("tasks:task_detail", pk=pk)
