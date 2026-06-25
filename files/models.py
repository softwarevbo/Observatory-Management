import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

"""
This module contains the database models for the Files / Document Management system.
It establishes schemas for directories, versions, file parameters, comments, annotations,
custom users access overrides, and system upload constraints.
"""

def upload_to(instance, filename):
    """
    Dynamically generates the physical file upload paths on disk.
    Structured as: projects/<project_id>/<folder>/<subfolder>/v<version>/<filename>
    This mimics the database category tree directly inside the server storage system.
    """
    # Resource Notes are saved under a separate category structure
    if instance.category and instance.category.name == "Notes":
        return f"resources/notes/{filename}"

    if instance.project:
        project_id = instance.project.project_id or f"PRJ-{instance.project.pk}"
        path_parts = [project_id]

        if instance.release:
            path_parts.append("Releases")
            path_parts.append(instance.release.name)
        else:
            # Traverses folders parent tree recursively to build paths
            if instance.category:
                cat = instance.category
                cat_parts = []
                while cat:
                    cat_parts.append(cat.name)
                    cat = cat.parent
                path_parts.extend(reversed(cat_parts))

            # Include version segment if this represents an edit revision update
            if getattr(instance, "version", 1) > 1:
                path_parts.append(f"v{instance.version}")

        return os.path.join("projects", *path_parts, filename).replace("\\", "/")

    # Redirection path for global uploads lacking specific project links
    uid = uuid.uuid4().hex[:8]
    now = timezone.now()
    return f"uploads/{now.year}/{now.month:02d}/{uid}/{filename}"


class FileCategory(models.Model):
    """
    Model representing subdirectories within projects.
    Allows infinite folder hierarchies by linking parent references to 'self'.
    """
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    project = models.ForeignKey(
        "tasks.Project", on_delete=models.CASCADE, related_name="file_categories"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "File Categories"
        ordering = ["name"]

    # Soft-deletion parameters
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_categories",
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return f"{self.project.name} / {self.name}"

    @property
    def latest_files(self):
        """Returns only the primary version of untrashed files inside this folder."""
        return self.files.filter(versions__isnull=True, is_in_trash=False).order_by("original_name")

    @property
    def full_path(self):
        return str(self)

    @property
    def project_relative_path(self):
        """Constructs folder relative path (e.g. 'Schematics/Chassis')."""
        path_parts = []
        cat = self
        while cat:
            path_parts.append(cat.name)
            cat = cat.parent
        path_parts.reverse()
        return "/".join(path_parts) if path_parts else ""

    @property
    def display_name(self):
        return self.name

    @property
    def physical_dir_path(self):
        """
        Returns the absolute filesystem path for this category's physical directory
        under media/projects/<project_id>/... mirroring the category tree.
        Returns None if the category has no project attached.
        """
        if not self.project:
            return None
        try:
            project_id = self.project.project_id or f"PRJ-{self.project.pk}"
            parts = []
            cat = self
            while cat:
                parts.append(cat.name)
                cat = cat.parent
            parts.reverse()
            return os.path.join(settings.MEDIA_ROOT, "projects", project_id, *parts)
        except Exception:
            return None

    def update_descendant_files(self):
        """Recursively updates the database file path of all files in this category and all subcategories."""
        for pf in self.files.all():
            pf.save()
        for child in self.children.all():
            child.update_descendant_files()

    def save(self, *args, **kwargs):
        """
        Overrides save() to keep the physical filesystem directory in sync with DB records.
        - New folder  → creates matching physical directory under media/projects/.
        - Renamed/moved folder → moves/renames the physical directory and propagates
          updated file paths to all nested ProjectFile records and sub-folders.
        """
        # Skip rename/sync logic on bulk-trash field updates to avoid recursion
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            super().save(*args, **kwargs)
            return

        is_new = not self.pk
        old_physical_path = None
        old_name = None

        if not is_new:
            try:
                old_obj = FileCategory.objects.select_related('project', 'parent').get(pk=self.pk)
                old_name = old_obj.name
                old_physical_path = old_obj.physical_dir_path
            except FileCategory.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # ── Create physical directory for newly created folder ──────────────────
        if is_new:
            try:
                phys = self.physical_dir_path
                if phys:
                    os.makedirs(phys, exist_ok=True)
            except Exception:
                pass  # Non-blocking — DB record already saved successfully

        # ── Sync physical directory when folder is renamed or re-parented ────────
        elif old_physical_path is not None:
            new_phys = self.physical_dir_path
            if new_phys and old_physical_path != new_phys:
                try:
                    import shutil
                    if os.path.isdir(old_physical_path):
                        os.makedirs(os.path.dirname(new_phys), exist_ok=True)
                        shutil.move(old_physical_path, new_phys)
                    else:
                        # Old directory absent — create the new path cleanly
                        os.makedirs(new_phys, exist_ok=True)
                except Exception:
                    pass  # Non-blocking — DB rename already succeeded

                # Propagate updated DB file-path records recursively to all descendant files
                self.update_descendant_files()
            elif old_name is not None and old_name != self.name:
                # Name changed but computed path is identical (e.g., no project set)
                self.update_descendant_files()


class ProjectFile(models.Model):
    """
    Model representing files attached to projects, requirements, or tasks.
    Supports version chains, soft-deletion workflows, and security access controls.
    """
    # Extension classification sets
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff"}
    PDF_EXTS = {".pdf"}
    DOC_EXTS = {".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".rst"}
    SHEET_EXTS = {".xls", ".xlsx", ".csv", ".ods"}
    SLIDE_EXTS = {".ppt", ".pptx", ".odp"}
    CODE_EXTS = {
        ".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".json",
        ".xml", ".yaml", ".yml", ".toml", ".ini", ".sh", ".bat", ".sql", ".php",
        ".rb", ".go", ".rs", ".swift", ".kt", ".r", ".m"
    }
    ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tar.gz"}
    VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}
    AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    CAD_EXTS = {".dwg", ".dxf", ".step", ".stp", ".iges", ".igs", ".stl", ".obj", ".3ds"}

    FILE_TYPE_CHOICES = [
        ("image", "Image"),
        ("pdf", "PDF"),
        ("document", "Document"),
        ("spreadsheet", "Spreadsheet"),
        ("presentation", "Presentation"),
        ("code", "Code / Script"),
        ("archive", "Archive"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("cad", "CAD / 3D"),
        ("other", "Other"),
    ]

    # File attributes
    file = models.FileField(upload_to=upload_to, max_length=500)
    original_name = models.CharField(max_length=300)
    file_size = models.PositiveBigIntegerField(default=0)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default="other")
    extension = models.CharField(max_length=20, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)

    # Scopes
    project = models.ForeignKey("tasks.Project", on_delete=models.CASCADE, related_name="files", null=True, blank=True)
    module = models.ForeignKey("tasks.ProjectModule", on_delete=models.SET_NULL, related_name="files", null=True, blank=True)
    release = models.ForeignKey("tasks.Release", on_delete=models.SET_NULL, related_name="direct_files", null=True, blank=True)
    task = models.ForeignKey("tasks.Task", on_delete=models.SET_NULL, related_name="files", null=True, blank=True)
    requirement = models.ForeignKey("tasks.Requirement", on_delete=models.SET_NULL, related_name="files", null=True, blank=True)
    category = models.ForeignKey(FileCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="files")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_files")
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_files",
    )

    # Metadata & Version control parameters
    title = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(
        default=False,
        help_text="If True, all project members can download; else only uploader and admin",
    )
    version = models.PositiveSmallIntegerField(default=1)
    # Self-referencing link for version chains (points to primary/version-1 file)
    parent_file = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versions",
        verbose_name="Previous Version",
    )
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft-deletion flags and double approval requirements (needs Admin + PM verification)
    is_in_trash = models.BooleanField(default=False)
    hidden_from_user_trash = models.BooleanField(default=False)
    admin_approved_deletion = models.BooleanField(default=False)
    pm_approved_deletion = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_files",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Project File"

    def __str__(self):
        return self.display_name

    @property
    def full_path(self):
        """Constructs logical hierarchy path (e.g. 'Project Alpha / Schematic / blueprint.pdf')."""
        path_parts = [self.project.name] if self.project else ["(No Project)"]
        cat = self.category
        cat_parts = []
        while cat:
            cat_parts.append(cat.name)
            cat = cat.parent
        path_parts.extend(reversed(cat_parts))
        path_parts.append(self.original_name)
        return " / ".join(path_parts)

    def get_project_relative_path(self):
        """Constructs project relative path (e.g. 'Schematic/blueprint.pdf')."""
        path_parts = []
        cat = self.category
        while cat:
            path_parts.append(cat.name)
            cat = cat.parent
        path_parts.reverse()
        path_parts.append(self.original_name)
        return os.path.join(*path_parts) if path_parts else self.original_name

    @property
    def display_name(self):
        return self.title or self.original_name

    @property
    def name(self):
        return self.display_name

    @property
    def file_size_display(self):
        """Converts raw byte sizes to readable string formats."""
        size = self.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024**2:
            return f"{size / 1024:.1f} KB"
        elif size < 1024**3:
            return f"{size / 1024**2:.1f} MB"
        return f"{size / 1024**3:.1f} GB"

    @property
    def icon_class(self):
        """Returns matching FontAwesome class representation."""
        return {
            "image": "fa-file-image",
            "pdf": "fa-file-pdf",
            "document": "fa-file-word",
            "spreadsheet": "fa-file-excel",
            "presentation": "fa-file-powerpoint",
            "code": "fa-file-code",
            "archive": "fa-file-archive",
            "video": "fa-file-video",
            "audio": "fa-file-audio",
            "cad": "fa-cube",
        }.get(self.file_type, "fa-file")

    @property
    def icon_color(self):
        """Returns matching hex color representation."""
        return {
            "image": "#06b6d4",
            "pdf": "#ef4444",
            "document": "#4f8ef7",
            "spreadsheet": "#22c55e",
            "presentation": "#f97316",
            "code": "#a855f7",
            "archive": "#f59e0b",
            "video": "#ec4899",
            "audio": "#8b5cf6",
            "cad": "#64748b",
        }.get(self.file_type, "#7a8aaa")

    @property
    def is_previewable(self):
        """Identifies files that can render inside browser layouts directly."""
        return (
            self.file_type in ("image", "pdf")
            or (self.file_type == "code" and self.file_size < 500_000)
            or (
                self.file_type == "document"
                and self.extension in {".txt", ".md", ".rst"}
                and self.file_size < 500_000
            )
        )

    @property
    def is_text_viewable(self):
        """Identifies files containing plaintext suitable for the online editor."""
        return self.file_type == "code" or self.extension in {
            ".txt", ".md", ".rst", ".log", ".ini", ".cfg", ".toml", ".yaml", ".yml",
            ".json", ".xml", ".csv",
        }

    @property
    def is_image(self):
        return self.file_type == "image"

    @property
    def is_pdf(self):
        return self.file_type == "pdf"

    @classmethod
    def detect_file_type(cls, extension):
        """Resolves file extension string into category names."""
        ext = extension.lower()
        if ext in cls.IMAGE_EXTS:
            return "image"
        if ext in cls.PDF_EXTS:
            return "pdf"
        if ext in cls.DOC_EXTS:
            return "document"
        if ext in cls.SHEET_EXTS:
            return "spreadsheet"
        if ext in cls.SLIDE_EXTS:
            return "presentation"
        if ext in cls.CODE_EXTS:
            return "code"
        if ext in cls.ARCHIVE_EXTS:
            return "archive"
        if ext in cls.VIDEO_EXTS:
            return "video"
        if ext in cls.AUDIO_EXTS:
            return "audio"
        if ext in cls.CAD_EXTS:
            return "cad"
        return "other"

    def save(self, *args, **kwargs):
        """
        Overrides save() to detect sizes and category parameters.
        Tracks movement and renames on disk to match directory structures.
        """
        if self.file and not self.pk:
            name = os.path.basename(self.file.name)
            if not self.original_name:
                self.original_name = name
            ext = os.path.splitext(name)[1].lower()
            self.extension = ext
            self.file_type = self.detect_file_type(ext)
            self.file_size = self.file.size

        # Handles disk migrations when project or category attributes change
        if self.pk:
            old_instance = ProjectFile.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.file and self.file:
                current_basename = os.path.basename(self.file.name) if self.file.name else self.original_name
                new_path = self.upload_to_path(current_basename)
                if old_instance.file.name != new_path:
                    import shutil
                    from django.conf import settings

                    old_full_path = old_instance.file.path
                    new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)

                    if os.path.exists(old_full_path):
                        os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                        shutil.move(old_full_path, new_full_path)
                    self.file.name = new_path

        super().save(*args, **kwargs)

    def upload_to_path(self, filename):
        return upload_to(self, filename)


class FileComment(models.Model):
    """
    Model representing discussion comments on files or folders.
    Supports PDF page annotations (coords logs), color highlight tracking, and thread replies.
    """
    file = models.ForeignKey(
        ProjectFile, on_delete=models.CASCADE, null=True, blank=True, related_name="comments"
    )
    category = models.ForeignKey(
        FileCategory, on_delete=models.CASCADE, null=True, blank=True, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Self-referencing link for discussion replies tree structure
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    
    # PDF Annotation coordinates
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=255, blank=True, null=True)
    highlight_color = models.CharField(max_length=50, default="#ffeb3b")
    annotation_coords = models.TextField(blank=True, null=True) # JSON coordinates array string
    
    # Optional assignee parameter to assign tasks within discussions
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_comments",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        target = self.file if self.file else self.category
        return f"Comment by {self.author} on {target}"


class DocumentAccessRight(models.Model):
    """
    Model representing explicit access overrides for files or Knowledge Base notes.
    Permits granular view/edit/delete adjustments outside project scope.
    """
    file = models.ForeignKey(
        ProjectFile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_rights",
    )
    kb_note = models.ForeignKey(
        "notes.KnowledgeBaseNote",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_rights",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_access_rights",
    )
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        doc = self.file or self.kb_note
        return f"Access for {self.user} on {doc}"


class SystemSettings(models.Model):
    """
    Model representing system-wide upload size limitations.
    """
    max_file_size_gb = models.PositiveIntegerField(
        default=10, help_text="Maximum file upload size in GB (Max 50GB)"
    )

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Global Settings (Max Size: {self.max_file_size_gb}GB)"

    @classmethod
    def get_max_size_bytes(cls):
        """Assembles maximum size threshold in bytes for validation checks."""
        try:
            config = cls.objects.first()
            if config:
                return config.max_file_size_gb * 1024 * 1024 * 1024
        except:
            pass
        return 10 * 1024 * 1024 * 1024 # Default fallback to 10GB
