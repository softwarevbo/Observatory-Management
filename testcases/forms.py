from django import forms
from tasks.models import Project, Task
from .models import TestCase, TestCaseComment


class TestCaseForm(forms.ModelForm):
    class Meta:
        model = TestCase
        fields = [
            "project",
            "task",
            "title",
            "scenario",
            "preconditions",
            "steps",
            "expected_result",
            "actual_result",
            "priority",
            "status",
            "assigned_members",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Test Case Title"}),
            "scenario": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Test Scenario"}),
            "preconditions": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Preconditions"}),
            "steps": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Test Steps"}),
            "expected_result": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Expected Result"}),
            "actual_result": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Actual Result"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "project": forms.Select(attrs={"class": "form-control"}),
            "task": forms.Select(attrs={"class": "form-control"}),
            "assigned_members": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        from tasks.models import Project, Task
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if project:
            self.fields["project"].initial = project
            self.fields["project"].widget = forms.HiddenInput()
            self.fields["task"].queryset = Task.objects.filter(project=project, is_in_trash=False).exclude(linked_bugs__is_in_trash=True).order_by("title")
            
            member_ids = list(project.members.values_list("pk", flat=True))
            member_ids.extend(project.managers.values_list("pk", flat=True))
            self.fields["assigned_members"].queryset = User.objects.filter(pk__in=member_ids, is_active=True).order_by("first_name")
        else:
            curr_project_id = self.data.get(self.add_prefix("project")) or (self.instance.project_id if self.instance.pk else None)
            
            if curr_project_id:
                try:
                    curr_project = Project.objects.get(pk=curr_project_id)
                    self.fields["task"].queryset = Task.objects.filter(project=curr_project, is_in_trash=False).exclude(linked_bugs__is_in_trash=True).order_by("title")
                    member_ids = list(curr_project.members.values_list("pk", flat=True))
                    member_ids.extend(curr_project.managers.values_list("pk", flat=True))
                    self.fields["assigned_members"].queryset = User.objects.filter(pk__in=member_ids, is_active=True).order_by("first_name")
                except:
                    self.fields["task"].queryset = Task.objects.none()
                    self.fields["assigned_members"].queryset = User.objects.none()
            else:
                self.fields["task"].queryset = Task.objects.none()
                self.fields["assigned_members"].queryset = User.objects.none()

        self.fields["assigned_members"].required = True
        self.fields["status"].required = True
        self.fields["title"].required = True
        self.fields["project"].required = False if project else True
        self.fields["task"].required = True


class TestCaseCommentForm(forms.ModelForm):
    class Meta:
        model = TestCaseComment
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a comment to the test case forum...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }
