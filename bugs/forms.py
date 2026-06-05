from django import forms
from django.db.models import Q
from accounts.models import User
from tasks.models import Project, Task
from .models import BugReport, BugComment

"""
This module defines Django ModelForms for:
1. BugReportForm: Reporting or editing software/hardware bugs.
2. BugCommentForm: Writing and attaching logs/images on bug pages.
3. BugResolutionForm: Detailing resolution summaries, attachment links, and status changes.

The forms implement dynamic field querying in `__init__` constructor overrides, 
restricting project fields, assignees, and companion tasks based on the active user context.
"""

class BugReportForm(forms.ModelForm):
    """
    Form used to submit or update bug reports.
    Customizes field widgets and dynamically filters options in the constructor.
    """
    class Meta:
        model = BugReport
        fields = [
            "title",
            "project",
            "severity",
            "description",
            "steps_to_reproduce",
            "expected_behavior",
            "actual_behavior",
            "assignees",
            "linked_task",
            "status",
        ]
        # HTML element attribute styling overrides
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Short descriptive title",
                }
            ),
            "project": forms.Select(
                attrs={"class": "form-control", "id": "id_bug_project"}
            ),
            "severity": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What went wrong?",
                }
            ),
            "steps_to_reproduce": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "1. Go to...\n2. Click on...\n3. See error",
                }
            ),
            "expected_behavior": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "What should happen?",
                }
            ),
            "actual_behavior": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "What actually happened?",
                }
            ),
            # SelectMultiple widget allows choosing multiple user assignees
            "assignees": forms.SelectMultiple(attrs={"class": "form-control"}),
            "linked_task": forms.Select(
                attrs={"class": "form-control", "id": "id_linked_task"}
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        """
        Dynamically filters dropdown options based on the user's role and selected project.
        """
        super().__init__(*args, **kwargs)
        
        # Pre-select project if specified
        if project:
            self.fields["project"].initial = project
            
        # Determine target project context (from argument, or from existing model instance)
        target_project = project or (
            self.instance.project if self.instance and self.instance.pk else None
        )
        
        if target_project:
            # Gather all member and manager primary keys belonging to the selected project
            member_ids = list(target_project.members.values_list("pk", flat=True))
            member_ids.extend(target_project.managers.values_list("pk", flat=True))
            
            # Restrict selectable assignees list to active project members/managers only
            self.fields["assignees"].queryset = User.objects.filter(
                pk__in=member_ids, is_active=True
            ).order_by("first_name", "username")
            
            # Restrict selectable companion tasks to untrashed tasks belonging to this project
            self.fields["linked_task"].queryset = Task.objects.filter(
                project=target_project, is_in_trash=False
            ).exclude(linked_bugs__is_in_trash=True).order_by("title")
        else:
            # No project selected yet: fallbacks
            self.fields["assignees"].queryset = User.objects.filter(
                is_active=True
            ).order_by("first_name")
            
            if user and not user.is_admin:
                # Restrict tasks choices to projects accessible to the user
                accessible = Project.objects.filter(
                    Q(managers=user) | Q(members=user)
                ).distinct()
                self.fields["linked_task"].queryset = Task.objects.filter(
                    project__in=accessible, is_in_trash=False
                ).exclude(linked_bugs__is_in_trash=True).order_by("title")
            else:
                self.fields["linked_task"].queryset = Task.objects.filter(is_in_trash=False).exclude(linked_bugs__is_in_trash=True).order_by(
                    "title"
                )

        # Assignees is not a mandatory field when reporting a bug
        self.fields["assignees"].required = False
        
        # ─── Security Restriction: Only Project Managers or Admins can assign bugs ───
        can_assign = False
        if user:
            if user.is_admin or user.is_project_manager:
                can_assign = True
            elif target_project and (target_project.managers.filter(pk=user.pk).exists() or target_project.project_incharge == user):
                can_assign = True
        
        if not can_assign:
            self.fields["assignees"].disabled = True
            self.fields["assignees"].help_text = "Only Project Managers can assign bugs."

        # Field presentation formatting
        self.fields["linked_task"].empty_label = "— None —"
        self.fields["status"].required = False
        self.fields["project"].required = False
        
        # If the bug is already reported, check if standard assignee tries to modify it.
        # Assignees can only update bug 'status', all other fields must be read-only for them.
        if self.instance and self.instance.pk and user:
            is_assignee = self.instance.assignees.filter(pk=user.pk).exists()
            if (
                is_assignee
                and user != self.instance.reported_by
                and not getattr(user, "is_admin", False)
            ):
                for field_name, field in self.fields.items():
                    if field_name != "status":
                        field.disabled = True
                        
        # Restrict the project choice dropdown list to projects where the user is a manager or member
        if user and not user.is_admin:
            self.fields["project"].queryset = Project.objects.filter(
                Q(managers=user) | Q(members=user)
            ).distinct()

    def clean(self):
        """
        Validates form inputs: ensures assignees selected belong to the chosen project context.
        """
        cleaned_data = super().clean()
        project, assignees = cleaned_data.get("project"), cleaned_data.get("assignees")
        
        if project and assignees:
            # Get valid project member and manager ID list
            member_ids = list(project.members.values_list("pk", flat=True)) + list(
                project.managers.values_list("pk", flat=True)
            )
            for assignee in assignees:
                if assignee.pk not in member_ids:
                    # Append error to the 'assignees' field context
                    self.add_error(
                        "assignees",
                        f"The assigned user ({assignee.display_name}) must be a member or manager of the selected project.",
                    )
        return cleaned_data


class BugCommentForm(forms.ModelForm):
    """
    Form used to submit comments and attachments on bug reports.
    """
    class Meta:
        model = BugComment
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Write a comment...",
                    "style": "border-radius: 20px; padding: 10px 15px; resize: none;",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }


class BugResolutionForm(forms.ModelForm):
    """
    Form used by developers or managers to log resolution summaries and close bugs.
    """
    class Meta:
        model = BugReport
        fields = [
            "resolution_summary",
            "solving_results",
            "resolution_attachment",
            "status",
        ]
        widgets = {
            "resolution_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "What was the cause and how was it fixed?",
                }
            ),
            "solving_results": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "What are the results after fixing?",
                }
            ),
            "resolution_attachment": forms.FileInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, is_leadership=False, **kwargs):
        """
        Dynamically restricts selectable status transitions depending on leadership role status.
        Only admins/project managers can close a ticket, standard developers can only set it to 'Resolved'.
        """
        super().__init__(*args, **kwargs)
        if is_leadership:
            self.fields["status"].choices = [
                ("resolved", "Resolved"),
                ("closed", "Closed"),
                ("wont_fix", "Won't Fix"),
            ]
        else:
            self.fields["status"].choices = [
                ("resolved", "Resolved"),
                ("wont_fix", "Won't Fix"),
            ]
