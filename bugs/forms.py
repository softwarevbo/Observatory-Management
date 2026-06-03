from django import forms
from django.db.models import Q
from accounts.models import User
from tasks.models import Project, Task
from .models import BugReport, BugComment


class BugReportForm(forms.ModelForm):
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
            "assignees": forms.SelectMultiple(attrs={"class": "form-control"}),
            "linked_task": forms.Select(
                attrs={"class": "form-control", "id": "id_linked_task"}
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.fields["project"].initial = project
        target_project = project or (
            self.instance.project if self.instance and self.instance.pk else None
        )
        if target_project:
            member_ids = list(target_project.members.values_list("pk", flat=True))
            member_ids.extend(target_project.managers.values_list("pk", flat=True))
            self.fields["assignees"].queryset = User.objects.filter(
                pk__in=member_ids, is_active=True
            ).order_by("first_name", "username")
            self.fields["linked_task"].queryset = Task.objects.filter(
                project=target_project, is_in_trash=False
            ).exclude(linked_bugs__is_in_trash=True).order_by("title")
        else:
            self.fields["assignees"].queryset = User.objects.filter(
                is_active=True
            ).order_by("first_name")
            if user and not user.is_admin:
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

        self.fields["assignees"].required = False
        
        # Restriction: Only PM or Admin can assign bugs
        can_assign = False
        if user:
            if user.is_admin or user.is_project_manager:
                can_assign = True
            elif target_project and (target_project.managers.filter(pk=user.pk).exists() or target_project.project_incharge == user):
                can_assign = True
        
        if not can_assign:
            self.fields["assignees"].disabled = True
            self.fields["assignees"].help_text = "Only Project Managers can assign bugs."

        self.fields["linked_task"].empty_label = "— None —"
        self.fields["status"].required = False
        self.fields["project"].required = False
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
        if user and not user.is_admin:
            self.fields["project"].queryset = Project.objects.filter(
                Q(managers=user) | Q(members=user)
            ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        project, assignees = cleaned_data.get("project"), cleaned_data.get("assignees")
        if project and assignees:
            member_ids = list(project.members.values_list("pk", flat=True)) + list(
                project.managers.values_list("pk", flat=True)
            )
            for assignee in assignees:
                if assignee.pk not in member_ids:
                    self.add_error(
                        "assignees",
                        f"The assigned user ({assignee.display_name}) must be a member or manager of the selected project.",
                    )
        return cleaned_data


class BugCommentForm(forms.ModelForm):
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
