from django import forms
from ..models import Project, Release, Requirement, ReleaseDeletionRequest
from files.models import ProjectFile, FileCategory


class ReleaseForm(forms.ModelForm):
    class Meta:
        model = Release
        fields = [
            "name",
            "tag_name",
            "release_type",
            "status",
            "version",
            "target_date",
            "is_draft",
            "is_prerelease",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. May 2025 Release"}
            ),
            "tag_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. v1.0.0"}
            ),
            "release_type": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "target_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_draft": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_prerelease": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Write release notes in Markdown...",
                }
            ),
        }

    def __init__(self, *args, project=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

        if not project and user:
            qs = (
                Project.objects.all()
                if user.is_admin
                else Project.objects.filter(managers=user)
            )
            self.fields["project"] = forms.ModelChoiceField(
                queryset=qs,
                widget=forms.Select(attrs={"class": "form-control"}),
                required=True,
            )

        if project:
            # Only show top-level files (not those that are old versions)
            from django.db.models import Max
            latest_versions = ProjectFile.objects.filter(project=project).values('original_name', 'category').annotate(max_version=Max('version'))
            
            # This is complex in a single queryset, let's keep it simple for now and just show all files but labeled with version
            self.fields["selected_files"] = forms.ModelMultipleChoiceField(
                queryset=ProjectFile.objects.filter(project=project).order_by(
                    "category__name", "original_name", "-version"
                ),
                widget=forms.CheckboxSelectMultiple,
                required=False,
                label="Select Specific Files to Include",
            )
            
            self.fields["selected_folders"] = forms.ModelMultipleChoiceField(
                queryset=FileCategory.objects.filter(project=project).order_by("name"),
                widget=forms.CheckboxSelectMultiple,
                required=False,
                label="Select Folders to Include",
            )
            
            self.fields["include_subfolders"] = forms.BooleanField(
                required=False,
                initial=True,
                label="Automatically include all files and subfolders inside selected folders",
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )

            if self.instance and self.instance.pk:
                release_pfs = ProjectFile.objects.filter(
                    release_mappings__release=self.instance
                )
                released_file_ids = set()
                for pf in release_pfs:
                    latest_pf = ProjectFile.objects.filter(
                        project=project,
                        category=pf.category,
                        original_name=pf.original_name,
                        versions__isnull=True,
                        is_in_trash=False
                    ).first()
                    if latest_pf:
                        released_file_ids.add(latest_pf.id)
                    else:
                        released_file_ids.add(pf.id)
                
                self.fields["selected_files"].initial = ProjectFile.objects.filter(id__in=released_file_ids)
                
                # A folder category should only be checked on load if ALL of its active descendant files are in the release
                all_categories = FileCategory.objects.filter(project=project)
                selected_cat_ids = []
                
                for cat in all_categories:
                    descendant_files = []
                    def collect_descendants(c):
                        descendant_files.extend(list(ProjectFile.objects.filter(
                            category=c, 
                            project=project, 
                            versions__isnull=True, 
                            is_in_trash=False
                        )))
                        for child in c.children.all():
                            collect_descendants(child)
                            
                    collect_descendants(cat)
                    
                    if descendant_files and all(f.id in released_file_ids for f in descendant_files):
                        selected_cat_ids.append(cat.id)
                        
                self.fields["selected_folders"].initial = FileCategory.objects.filter(id__in=selected_cat_ids)
        else:
            self.fields["selected_files"] = forms.ModelMultipleChoiceField(
                queryset=ProjectFile.objects.none(),
                widget=forms.CheckboxSelectMultiple,
                required=False,
            )
            self.fields["selected_folders"] = forms.ModelMultipleChoiceField(
                queryset=FileCategory.objects.none(),
                widget=forms.CheckboxSelectMultiple,
                required=False,
            )
            self.fields["include_subfolders"] = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        project = self.project or cleaned_data.get("project")

        if name and project:
            qs = Release.objects.filter(project=project, name=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", f"A release named '{name}' already exists for this project.")
        return cleaned_data


class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = ["req_id", "name", "description", "requirement_type", "status", "priority", "assigned_team", "module"]
        widgets = {
            "req_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Requirement ID (Auto-generated if empty)",
                }
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Requirement name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Details of the requirement...",
                }
            ),
            "requirement_type": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "assigned_team": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Frontend Team"}),
            "module": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["req_id"].required = False
        self.fields["name"].required = False
        
        if not project and self.instance and self.instance.pk and self.instance.project:
            project = self.instance.project
            
        if project:
            self.fields["module"].queryset = project.modules.all()
        else:
            from ..models import ProjectModule
            self.fields["module"].queryset = ProjectModule.objects.all()
class ReleaseDeletionRequestForm(forms.ModelForm):
    from ..models import ReleaseDeletionRequest
    class Meta:
        model = ReleaseDeletionRequest
        fields = ["reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Explain why this release needs to be deleted...",
                }
            ),
        }


class ReleaseAssetUploadForm(forms.Form):
    asset_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        label="Select File"
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief description (optional)"}),
        required=False
    )
