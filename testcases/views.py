from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.forms import modelformset_factory

from tasks.models import Project, Task, ProjectModule, Requirement
from tasks.decorators import manager_or_admin_required
from tasks.services.notification_service import NotificationService
from .models import TestCase, TestCaseAttachment, TestCaseHistory, TestCaseComment
from .forms import TestCaseForm, TestCaseCommentForm


@login_required
@manager_or_admin_required
def test_case_bulk_create(request, project_id):
    """
    Formset grid view allowing managers/admins to dynamically mass-create test cases for a project.
    """
    project = get_object_or_404(Project, pk=project_id)
    TestCaseFormSet = modelformset_factory(
        TestCase,
        form=TestCaseForm,
        extra=1,
        can_delete=True
    )

    if request.method == "POST":
        formset = TestCaseFormSet(
            request.POST,
            queryset=TestCase.objects.none(),
            form_kwargs={"project": project, "user": request.user},
        )
        if formset.is_valid():
            saved_count = 0
            for form in formset:
                # Bypass empty rows or fields marked for deletion
                if form.cleaned_data.get("title") and not form.cleaned_data.get("DELETE"):
                    instance = form.save(commit=False)
                    instance.project = project
                    instance.created_by = request.user
                    instance.save()
                    form.save_m2m()
                    saved_count += 1
            
            messages.success(request, f"{saved_count} test cases created successfully.")
            return redirect("tasks:project_detail", pk=project.pk)
        else:
            # Aggregate validation error feedback
            error_msg = "Please correct the following errors: "
            for i, form in enumerate(formset):
                if form.errors:
                    error_msg += f"[Row {i+1}: {form.errors.as_text()}] "
            messages.warning(request, error_msg)
    else:
        formset = TestCaseFormSet(
            queryset=TestCase.objects.none(),
            form_kwargs={"project": project, "user": request.user},
        )

    return render(request, "test_cases/test_case_bulk_form.html", {
        "formset": formset,
        "project": project,
        "title": "Bulk Add Test Cases"
    })


@login_required
def test_case_create(request, project_id):
    """
    Enforces authorization check and creates a single testcase with attachments and history logs.
    """
    project = get_object_or_404(Project, pk=project_id)
    
    is_pm = project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    
    if not (request.user.is_admin or is_pm or is_incharge):
        messages.error(request, "Only project managers and in-charge can create test cases.")
        return redirect("tasks:project_detail", pk=project.pk)
        
    if request.method == "POST":
        form = TestCaseForm(request.POST, project=project)
        if form.is_valid():
            test_case = form.save(commit=False)
            test_case.created_by = request.user
            test_case.save()
            form.save_m2m()
            
            # Save associated file attachments
            files = request.FILES.getlist('attachments')
            for f in files:
                TestCaseAttachment.objects.create(test_case=test_case, file=f)
            
            # Log audit creation event
            TestCaseHistory.objects.create(
                test_case=test_case,
                user=request.user,
                action="Created",
                details="Initial test case creation"
            )
            
            # Notify members assigned to this testcase run
            for member in test_case.assigned_members.all():
                if member != request.user:
                    NotificationService.create_notification(
                        recipient=member,
                        sender=request.user,
                        notification_type="test_assigned",
                        title=f"New Test Case Assigned: {test_case.test_id}",
                        message=f"You have been assigned to test case: {test_case.title}",
                        project=project,
                        test_case=test_case
                    )
            
            messages.success(request, f"Test Case {test_case.test_id} created successfully.")
            return redirect(f"/projects/{project_id}/?view=test_cases")
    else:
        task_id = request.GET.get("task")
        initial = {}
        if task_id:
            initial['task'] = task_id
        form = TestCaseForm(project=project, initial=initial)
    
    return render(request, "test_cases/test_case_form.html", {
        "form": form,
        "project": project,
        "title": "Create Test Case",
        "action": "Create"
    })


@login_required
def test_case_edit(request, pk):
    """
    Edits parameters of a test case. Prevents editing items currently moved to trash.
    """
    test_case = get_object_or_404(TestCase, pk=pk)
    project = test_case.project
    
    if test_case.is_in_trash:
        messages.error(request, "Cannot edit a test case that is in the trash.")
        return redirect("tasks:project_detail", pk=project.pk)

    is_pm = project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    
    if not (request.user.is_admin or is_pm or is_incharge or test_case.created_by == request.user):
        messages.error(request, "You do not have permission to edit this test case.")
        return redirect("tasks:project_detail", pk=project.pk)
        
    if request.method == "POST":
        form = TestCaseForm(request.POST, instance=test_case, project=project)
        if form.is_valid():
            test_case = form.save()
            
            TestCaseHistory.objects.create(
                test_case=test_case,
                user=request.user,
                action="Edited",
                details="Test case updated"
            )
            
            messages.success(request, f"Test Case {test_case.test_id} updated.")
            return redirect("tasks:project_detail", pk=project.pk)
    else:
        form = TestCaseForm(instance=test_case, project=project)
    
    return render(request, "test_cases/test_case_form.html", {
        "form": form,
        "project": project,
        "test_case": test_case,
        "title": "Edit Test Case",
        "action": "Update"
    })


@login_required
def test_case_delete(request, pk):
    """
    Soft-deletes a test case by flagging 'is_in_trash' as True.
    """
    test_case = get_object_or_404(TestCase, pk=pk)
    project = test_case.project
    
    if test_case.is_in_trash:
        messages.error(request, "This test case is already in the trash.")
        return redirect("tasks:project_detail", pk=project.pk)

    is_pm = project.managers.filter(pk=request.user.pk).exists()
    is_incharge = project.project_incharge == request.user
    
    if not (request.user.is_admin or is_pm or is_incharge):
        messages.error(request, "Only project managers and in-charge can delete test cases.")
        return redirect("tasks:project_detail", pk=project.pk)
        
    if request.method == "POST":
        test_case.is_in_trash = True
        test_case.deleted_at = timezone.now()
        test_case.deleted_by = request.user
        test_case.save()
        messages.success(request, f"Test Case {test_case.test_id} moved to trash.")
        return redirect("tasks:project_detail", pk=project.pk)
    return render(request, "projects/confirm_delete.html", {"obj": test_case, "obj_type": "Test Case"})


@login_required
def test_case_detail(request, pk):
    """
    Renders comments, history, parameters, and attachments of a single test case.
    """
    test_case = get_object_or_404(TestCase, pk=pk)
    
    if test_case.is_in_trash and not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "This test case is in the trash and can only be previewed by Admins or Project Managers.")
        return redirect("tasks:project_detail", pk=test_case.project.pk)
        
    comments = test_case.comments.filter(parent__isnull=True).select_related("author").all()
    comment_form = TestCaseCommentForm()
    
    return render(request, "test_cases/test_case_detail.html", {
        "test_case": test_case,
        "comments": comments,
        "comment_form": comment_form,
    })


@login_required
def test_case_verify(request, pk):
    """
    Updates testcase verification status (passed, failed, retest).
    Triggers completion ready notifications to PMs if all test cases for the parent task are verified.
    """
    test_case = get_object_or_404(TestCase, pk=pk)
    
    if test_case.is_in_trash:
        messages.error(request, "Cannot verify a test case that is in the trash.")
        return redirect("tasks:project_detail", pk=test_case.project.pk)

    is_admin = request.user.is_admin
    is_pm = request.user.is_project_manager or test_case.project.managers.filter(pk=request.user.pk).exists()
    is_assigned = test_case.assigned_members.filter(pk=request.user.pk).exists()
    
    if not (is_admin or is_pm or is_assigned):
        messages.error(request, "You do not have permission to verify this test case.")
        return redirect("tasks:project_detail", pk=test_case.project.pk)
    
    if request.method == "POST":
        status = request.POST.get("status")
        actual_result = request.POST.get("actual_result")
        comment = request.POST.get("comment")
        
        old_status = test_case.status
        test_case.status = status
        test_case.actual_result = actual_result
        test_case.verified_by = request.user
        test_case.verified_date = timezone.now()
        
        # Admins or PMs immediately mark as approved if verification is passed
        if is_admin or is_pm:
            test_case.approval_status = "approved" if status == "passed" else "pending"
        
        test_case.save()
        
        # Save verification attachment files
        files = request.FILES.getlist('attachments')
        for f in files:
            TestCaseAttachment.objects.create(
                test_case=test_case, 
                file=f, 
                description=f"Verification attachment by {request.user.display_name}"
            )
            
        TestCaseHistory.objects.create(
            test_case=test_case,
            user=request.user,
            action="Verified",
            details=f"Status changed from {old_status} to {status}. Comment: {comment}"
        )
        
        # Route notifications depending on status result
        if status == "passed":
            recipients = set(test_case.project.managers.all())
            if test_case.created_by:
                recipients.add(test_case.created_by)
            recipients.update(test_case.assigned_members.all())
            
            for r in recipients:
                if r != request.user:
                    NotificationService.create_notification(
                        recipient=r,
                        sender=request.user,
                        notification_type="test_approved",
                        title=f"Test Case Verified: {test_case.test_id}",
                        message=f"Test case '{test_case.title}' has been verified as PASSED by {request.user.display_name}.",
                        project=test_case.project,
                        test_case=test_case
                    )
        elif status == "failed":
            recipients = set(test_case.project.managers.all())
            if test_case.created_by:
                recipients.add(test_case.created_by)
            
            for r in recipients:
                if r != request.user:
                    NotificationService.create_notification(
                        recipient=r,
                        sender=request.user,
                        notification_type="test_failed",
                        title=f"Test Case Failed: {test_case.test_id}",
                        message=f"Test case '{test_case.title}' was marked as Failed by {request.user.display_name}.",
                        project=test_case.project,
                        test_case=test_case
                    )
        elif status == "retest":
            for member in test_case.assigned_members.all():
                if member != request.user:
                    NotificationService.create_notification(
                        recipient=member,
                        sender=request.user,
                        notification_type="retest_requested",
                        title=f"Re-test Requested: {test_case.test_id}",
                        message=f"A re-test has been requested for: {test_case.title}",
                        project=test_case.project,
                        test_case=test_case
                    )
        
        # Trigger parent task completion readiness alerts
        task = test_case.task
        if task.can_complete:
             for pm in task.project.managers.all():
                  NotificationService.create_notification(
                        recipient=pm,
                        sender=request.user,
                        notification_type="task_ready_completion",
                        title=f"Task Ready: {task.task_id}",
                        message=f"All test cases for task '{task.title}' have passed. Task is ready for completion.",
                        project=task.project,
                        task=task
                    )

        messages.success(request, f"Test Case {test_case.test_id} verification updated.")
        return redirect("tasks:project_detail", pk=test_case.project.pk)
    
    return render(request, "test_cases/test_case_verify.html", {
        "test_case": test_case,
        "status_choices": TestCase.STATUS_CHOICES
    })


@login_required
def test_case_comment_add(request, pk):
    """
    Appends a new discussion comment to a test case. Handles threaded reply associations.
    """
    test_case = get_object_or_404(TestCase, pk=pk)
    project = test_case.project
    
    is_member = (
        project.members.filter(pk=request.user.pk).exists()
        or project.managers.filter(pk=request.user.pk).exists()
        or request.user.is_admin
    )
    if not is_member:
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")
        
    if request.method == "POST":
        form = TestCaseCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.test_case = test_case
            comment.author = request.user
            parent_id = request.POST.get("parent_id")
            if parent_id:
                try:
                    comment.parent = TestCaseComment.objects.get(pk=parent_id)
                except TestCaseComment.DoesNotExist:
                    pass
            comment.save()
            
            # Send dynamic notifications to all project members
            recipients = set(project.members.all()) | set(project.managers.all())
            if project.project_incharge:
                recipients.add(project.project_incharge)
            
            for recipient in recipients:
                if recipient != request.user:
                    NotificationService.create_notification(
                        recipient=recipient,
                        sender=request.user,
                        notification_type="project_update",
                        title=f"New Comment on Test Case: {test_case.title}",
                        message=f"{request.user.display_name} commented on test case '{test_case.title}': {comment.content[:50]}...",
                        project=project,
                        test_case=test_case,
                    )
            
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Error adding comment.")
            
    return redirect("testcases:test_case_detail", pk=pk)
