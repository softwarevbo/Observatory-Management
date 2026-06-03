from django import forms
from django.db.models import Q
from django.forms.widgets import Input

from .models import FileCategory, FileComment, ProjectFile

# ── Multi-file widget — bypasses Django's ClearableFileInput restriction ──────


class MultipleFileInput(Input):
    """
    Raw <input type="file" multiple> widget.
    Subclasses Input directly to avoid the ValueError in FileInput.__init__
    that blocks the 'multiple' attribute.
    """

    input_type = "file"
    needs_multipart_form = True
    allow_multiple_selected = True

    def format_value(self, value):
        return None  # file inputs never have a pre-filled value

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files


class MultipleFileField(forms.FileField):
    """FileField that accepts and validates a list of uploaded files."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(
                attrs={
                    "class": "file-input-hidden",
                    "id": "multiFileInput",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(f, initial) for f in data]
        return single_file_clean(data, initial)


# ── Forms ─────────────────────────────────────────────────────────────────────


class FileUploadForm(forms.ModelForm):
    """Single-file upload form attached to a project / task."""

    class Meta:
        model = ProjectFile
        fields = [
            "file",
            "title",
            "description",
            "project",
            "task",
            "requirement",
            "category",
            "is_public",
            "parent_file",
        ]
        widgets = {
            "file": forms.FileInput(
                attrs={
                    "class": "file-input-hidden",
                    "id": "fileUploadInput",
                }
            ),
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional display title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "What is this file about?",
                }
            ),
            "project": forms.Select(attrs={"class": "form-control"}),
            "task": forms.Select(attrs={"class": "form-control"}),
            "requirement": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "parent_file": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, project=None, task=None, requirement=None, **kwargs):
        super().__init__(*args, **kwargs)
        from tasks.models import Project, Task, Requirement

        active_projects = Project.objects.filter(
            is_archived=False,
            deletion_requested_by_admin=False,
            deletion_requested_by_pm=False
        )
        if user and user.is_admin:
            self.fields["project"].queryset = active_projects
        elif user:
            self.fields["project"].queryset = active_projects.filter(
                Q(managers=user) | Q(members=user) | Q(project_incharge=user)
            ).distinct()
        else:
            self.fields["project"].queryset = Project.objects.none()

        self.fields["project"].empty_label = "— No project —"
        self.fields["project"].required = False

        if project:
            self.fields["task"].queryset = Task.objects.filter(project=project)
            self.fields["requirement"].queryset = Requirement.objects.filter(project=project)
            self.fields["category"].queryset = FileCategory.objects.filter(
                project=project, is_in_trash=False
            )
            self.fields["project"].initial = project
        else:
            self.fields["task"].queryset = Task.objects.none()
            self.fields["requirement"].queryset = Requirement.objects.none()
            self.fields["category"].queryset = FileCategory.objects.none()

        if task:
            self.fields["task"].initial = task
        if requirement:
            self.fields["requirement"].initial = requirement

        self.fields["task"].empty_label = "— No task —"
        self.fields["task"].required = False
        self.fields["requirement"].empty_label = "— No requirement —"
        self.fields["requirement"].required = False
        self.fields["category"].empty_label = "— No category —"
        self.fields["category"].required = False
        self.fields["category"].label_from_instance = lambda obj: obj.full_path
        self.fields["parent_file"].empty_label = "— New file (not a version) —"
        self.fields["parent_file"].required = False

        if project:
            self.fields["parent_file"].queryset = ProjectFile.objects.filter(
                project=project
            )
        else:
            self.fields["parent_file"].queryset = ProjectFile.objects.none()


class MultiFileUploadForm(forms.Form):
    """Drag-and-drop multi-file upload form."""

    files = MultipleFileField(label="Files", required=False)
    project = forms.ModelChoiceField(
        queryset=None,
        empty_label="— Select Project —",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    task = forms.ModelChoiceField(
        queryset=None,
        empty_label="— No task —",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Description for all files (optional)",
            }
        ),
    )
    category = forms.ModelChoiceField(
        queryset=None,
        empty_label="— No folder —",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    is_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from tasks.models import Project, Task

        active_projects = Project.objects.filter(
            is_archived=False,
            deletion_requested_by_admin=False,
            deletion_requested_by_pm=False
        )
        if user and user.is_admin:
            self.fields["project"].queryset = active_projects
        elif user:
            self.fields["project"].queryset = active_projects.filter(
                Q(managers=user) | Q(members=user) | Q(project_incharge=user)
            ).distinct()
        else:
            self.fields["project"].queryset = Project.objects.none()
        self.fields["task"].queryset = Task.objects.none()
        self.fields["category"].queryset = FileCategory.objects.none()


class FileCategoryForm(forms.ModelForm):
    class Meta:
        model = FileCategory
        fields = ["name", "project"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Schematics, Reports...",
                }
            ),
            "project": forms.Select(attrs={"class": "form-control"}),
        }


class FileEditForm(forms.ModelForm):
    class Meta:
        model = ProjectFile
        fields = ["title", "description", "category", "is_public"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.project:
            self.fields["category"].queryset = FileCategory.objects.filter(
                project=self.instance.project, is_in_trash=False
            )
        else:
            self.fields["category"].queryset = FileCategory.objects.none()
        self.fields["category"].required = False
        self.fields["category"].empty_label = "— No category —"
        self.fields["category"].label_from_instance = lambda obj: obj.full_path


class FileCommentForm(forms.ModelForm):
    class Meta:
        model = FileComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Add a comment on this file...",
                }
            )
        }
