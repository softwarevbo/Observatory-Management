from django import forms
from django.db.models import Q
from accounts.models import User
from ..models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "project_id",
            "name",
            "description",
            "module",
            "status",
            "priority",
            "visibility",
            "image",
            "background_color",
            "button_color",
            "start_date",
            "end_date",
            "managers",
            "incharges",
            "project_incharge",
            "members",
        ]
        widgets = {
            "project_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Project ID (Auto-generated if empty)",
                }
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Project name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Describe the project...",
                }
            ),
            "module": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "background_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "button_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "managers": forms.CheckboxSelectMultiple(),
            "incharges": forms.CheckboxSelectMultiple(),
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
            "members": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # All active users are eligible to be assigned as managers, incharges, or members
        self.fields["managers"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
        self.fields["incharges"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
        self.fields["project_incharge"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
        self.fields["members"].queryset = User.objects.filter(is_active=True).order_by(
            "team", "first_name", "username"
        )
        self.fields["managers"].required = False
        self.fields["incharges"].required = False
        self.fields["project_incharge"].required = False
        self.fields["members"].required = False
        self.fields["project_id"].required = False


class ProjectEditForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "module",
            "status",
            "priority",
            "visibility",
            "start_date",
            "end_date",
            "image",
            "background_color",
            "button_color",
            "managers",
            "incharges",
            "project_incharge",
            "members",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Project name"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "module": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "background_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color", "style": "height: 40px; padding: 2px;"}
            ),
            "button_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color", "style": "height: 40px; padding: 2px;"}
            ),
            "managers": forms.CheckboxSelectMultiple(),
            "incharges": forms.CheckboxSelectMultiple(),
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
            "members": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            members_qs = User.objects.filter(
                Q(projects=self.instance)
                | Q(managed_projects=self.instance)
                | Q(incharge_projects_set=self.instance)
                | Q(created_projects=self.instance)
            ).filter(is_active=True).distinct().order_by("first_name", "username")
        else:
            members_qs = User.objects.filter(is_active=True).order_by("first_name", "username")

        self.fields["managers"].queryset = members_qs
        self.fields["incharges"].queryset = members_qs
        self.fields["project_incharge"].queryset = members_qs
        self.fields["members"].queryset = User.objects.filter(is_active=True).order_by(
            "team", "first_name", "username"
        )
        self.fields["managers"].required = False
        self.fields["incharges"].required = False
        self.fields["members"].required = False
        self.fields["project_incharge"].required = False


class ProjectSettingsForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "module",
            "status",
            "priority",
            "visibility",
            "start_date",
            "end_date",
            "managers",
            "incharges",
            "image",
            "project_incharge",
            "background_color",
            "button_color",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Project name"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Describe the project..."}
            ),
            "module": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "background_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control",
                    "style": "height: 40px; padding: 2px;",
                }
            ),
            "button_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "form-control",
                    "style": "height: 40px; padding: 2px;",
                }
            ),
            "image": forms.FileInput(attrs={"class": "form-control"}),
            "managers": forms.CheckboxSelectMultiple(),
            "incharges": forms.CheckboxSelectMultiple(),
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            members_qs = User.objects.filter(
                Q(projects=self.instance)
                | Q(managed_projects=self.instance)
                | Q(incharge_projects_set=self.instance)
                | Q(created_projects=self.instance)
            ).filter(is_active=True).distinct().order_by("first_name", "username")
        else:
            members_qs = User.objects.filter(is_active=True).order_by("first_name", "username")

        self.fields["managers"].queryset = members_qs
        self.fields["incharges"].queryset = members_qs
        self.fields["project_incharge"].queryset = members_qs
        
        self.fields["managers"].required = False
        self.fields["incharges"].required = False
        self.fields["project_incharge"].required = False
