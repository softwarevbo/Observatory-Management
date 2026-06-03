from django import forms
from ..models import ProjectModule, ModuleForumPost


class ProjectModuleForm(forms.ModelForm):
    class Meta:
        model = ProjectModule
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Module Name"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ModuleForumPostForm(forms.ModelForm):
    class Meta:
        model = ModuleForumPost
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Start a discussion...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }
