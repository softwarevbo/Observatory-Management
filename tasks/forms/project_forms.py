from django import forms
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
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
            "members": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["managers"].queryset = User.objects.filter(
            is_active=True, role__in=["admin", "project_manager"]
        )
        self.fields["members"].queryset = User.objects.filter(is_active=True).order_by(
            "team", "first_name"
        )
        self.fields["managers"].required = False
        self.fields["project_incharge"].required = False
        self.fields["members"].required = False
        self.fields["project_id"].required = False
        if user and user.is_admin:
            for field in ["start_date", "members"]:
                if field in self.fields:
                    del self.fields[field]


class ProjectEditForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "status",
            "priority",
            "start_date",
            "end_date",
            "project_incharge",
            "members",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Project name"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_admin:
            self.fields["members"].queryset = User.objects.filter(is_active=True)
        self.fields["project_incharge"].queryset = User.objects.filter(is_active=True)
        self.fields["project_incharge"].required = False


class ProjectSettingsForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "module",
            "visibility",
            "managers",
            "image",
            "project_incharge",
            "background_color",
            "button_color",
        ]
        widgets = {
            "module": forms.Select(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
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
            "project_incharge": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        
        # Consistent with ProjectForm: Managers should be active users with admin or project_manager roles
        self.fields["managers"].queryset = User.objects.filter(
            is_active=True, role__in=["admin", "project_manager"]
        ).order_by("first_name", "username")
        
        # Incharge can be any active user
        self.fields["project_incharge"].queryset = User.objects.filter(
            is_active=True
        ).order_by("first_name", "username")
        
        self.fields["managers"].required = False
        self.fields["project_incharge"].required = False
