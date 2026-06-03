from django import forms
from accounts.models import User
from ..models import Task, Comment, RequirementComment


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "task_id",
            "title",
            "description",
            "project",
            "requirement",
            "module",
            "task_type",
            "status",
            "priority",
            "assignees",
            "sprint",
            "milestone",
            "story_points",
            "deadline",
            "due_date",
            "parent_task",
            "tags",
            "estimated_hours",
        ]
        widgets = {
            "task_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Task ID (Auto-generated if empty)",
                }
            ),
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "What needs to be done?"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Details, acceptance criteria...",
                }
            ),
            "project": forms.Select(
                attrs={"class": "form-control"}
            ),
            "requirement": forms.Select(
                attrs={"class": "form-control"}
            ),
            "module": forms.Select(
                attrs={"class": "form-control"}
            ),
            "task_type": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "sprint": forms.Select(attrs={"class": "form-control"}),
            "milestone": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Q1 Release"}),
            "story_points": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0"}),
            "assignees": forms.CheckboxSelectMultiple(
                attrs={"class": "checkbox-list"}
            ),
            "deadline": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "parent_task": forms.Select(attrs={"class": "form-control"}),
            "tags": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "tag1, tag2, tag3"}
            ),
            "estimated_hours": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.5", "placeholder": "0.0"}
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        from ..models import Project, ProjectModule, Requirement, Task
        from django.contrib.auth import get_user_model
        from django.db import models
        User = get_user_model()

        # If project is provided, lock down querysets and hide project field
        if project:
            from django import forms
            self.fields["project"].initial = project
            self.fields["project"].widget = forms.HiddenInput(attrs={"id": "id_task_project"})
            
            self.fields["module"].queryset = ProjectModule.objects.filter(project=project).order_by("name")
            self.fields["requirement"].queryset = Requirement.objects.filter(project=project, is_approved=True, is_in_trash=False).order_by("req_id")
            
            member_ids = list(project.members.values_list("pk", flat=True))
            member_ids.extend(project.managers.values_list("pk", flat=True))
            self.fields["assignees"].queryset = User.objects.filter(pk__in=member_ids, is_active=True).order_by("first_name")
            self.fields["parent_task"].queryset = Task.objects.filter(project=project, parent_task__isnull=True, is_in_trash=False).exclude(linked_bugs__is_in_trash=True)
            active_projects = Project.objects.filter(
                is_archived=False,
                deletion_requested_by_admin=False,
                deletion_requested_by_pm=False
            )
            if user and not user.is_admin:
                projects = active_projects.filter(models.Q(members=user) | models.Q(managers=user)).distinct()
            else:
                projects = active_projects

            self.fields["project"].queryset = projects.order_by("name")
            
            # Handle dynamic filtering based on selected project
            curr_project_id = self.data.get(self.add_prefix("project")) or (self.instance.project_id if self.instance.pk else None)
            
            if curr_project_id:
                try:
                    curr_project = Project.objects.get(pk=curr_project_id)
                    from ..models import Sprint
                    self.fields["module"].queryset = ProjectModule.objects.filter(project=curr_project).order_by("name")
                    self.fields["requirement"].queryset = Requirement.objects.filter(project=curr_project, is_approved=True, is_in_trash=False).order_by("req_id")
                    self.fields["sprint"].queryset = Sprint.objects.filter(project=curr_project, is_completed=False).order_by("-start_date")
                    
                    member_ids = list(curr_project.members.values_list("pk", flat=True))
                    member_ids.extend(curr_project.managers.values_list("pk", flat=True))
                    self.fields["assignees"].queryset = User.objects.filter(pk__in=member_ids, is_active=True).order_by("first_name")
                    self.fields["parent_task"].queryset = Task.objects.filter(project=curr_project, parent_task__isnull=True, is_in_trash=False).exclude(linked_bugs__is_in_trash=True)
                except (Project.DoesNotExist, ValueError, TypeError):
                    self.fields["module"].queryset = ProjectModule.objects.none()
                    self.fields["requirement"].queryset = Requirement.objects.none()
                    self.fields["assignees"].queryset = User.objects.none()
                    self.fields["parent_task"].queryset = Task.objects.none()
            else:
                self.fields["module"].queryset = ProjectModule.objects.none()
                self.fields["requirement"].queryset = Requirement.objects.none()
                self.fields["assignees"].queryset = User.objects.none()
                self.fields["parent_task"].queryset = Task.objects.none()

        # Final adjustments
        self.fields["project"].required = False if project else True
        self.fields["assignees"].required = False
        self.fields["requirement"].required = False
        self.fields["task_id"].required = False
        self.fields["parent_task"].required = False
        self.fields["parent_task"].empty_label = "— No parent task —"
        self.fields["module"].empty_label = "— No module selected —"
        self.fields["requirement"].empty_label = "— No requirement (Optional) —"


class BulkTaskForm(TaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        # Remove fields not needed for bulk
        for field in ["due_date", "deadline", "estimated_hours", "sprint", "milestone", "story_points"]:
            if field in self.fields:
                del self.fields[field]

    class Meta(TaskForm.Meta):
        widgets = {
            **TaskForm.Meta.widgets,
            "assignees": forms.CheckboxSelectMultiple(attrs={"class": "checkbox-list"}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a comment...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }


class RequirementCommentForm(forms.ModelForm):
    class Meta:
        model = RequirementComment
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a comment to the requirement forum...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }
