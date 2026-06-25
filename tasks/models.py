from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
import random
import string
import os
import hashlib


class Project(models.Model):
    MODULE_CHOICES = [
        ("electronics", "Electronics"),
        ("mechanical", "Mechanical"),
        ("optics", "Optics"),
        ("simulation", "Simulation"),
        ("software", "Software"),
    ]
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("archived", "Archived"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    VISIBILITY_CHOICES = [
        ("private", "Private (Members Only)"),
        ("public", "Public (All Users)"),
    ]

    project_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    module = models.CharField(
        max_length=20, choices=MODULE_CHOICES, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default="private"
    )
    background_color = models.CharField(max_length=7, default="#ffffff")
    button_color = models.CharField(max_length=7, default="#4f8ef7")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_projects",
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_projects"
    )
    project_incharge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incharge_projects",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="projects"
    )
    progress = models.PositiveIntegerField(default=0)  # 0-100
    deletion_requested_by_admin = models.BooleanField(default=False)
    deletion_requested_by_pm = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    is_released = models.BooleanField(default=False)
    image = models.ImageField(upload_to="project_images/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.project_id}] {self.name}" if self.project_id else self.name

    @property
    def is_overdue(self):
        if self.end_date:
            return self.end_date < timezone.now().date() and self.status not in [
                "completed",
                "cancelled",
            ]
        return False

    @property
    def task_count(self):
        return self.tasks.filter(is_in_trash=False).count()

    @property
    def completed_task_count(self):
        return self.tasks.filter(is_in_trash=False, status="done").count()

    @property
    def latest_files(self):
        """Returns only the latest version of each active file (root files) for this project."""
        return self.files.filter(versions__isnull=True, is_in_trash=False).order_by("original_name")

    def update_progress(self):
        tasks = self.tasks.filter(is_in_trash=False)
        total_tasks = tasks.count()
        if total_tasks == 0:
            self.progress = 0
        else:
            total_progress = 0
            for task in tasks:
                task_weight = 0
                if task.status == "done":
                    task_weight = 100
                elif task.status == "review":
                    task_weight = 80
                elif task.status == "in_progress":
                    task_weight = 30
                
                # Factor in test cases if they exist
                stats = task.test_case_stats
                if stats["total"] > 0:
                    # If there are test cases, the task progress is a mix of status and test results
                    # Status is 60%, Test results are 40%
                    tc_factor = stats["percentage"]
                    task_weight = int((task_weight * 0.6) + (tc_factor * 0.4))
                
                total_progress += task_weight
            
            self.progress = int(total_progress / total_tasks)
        self.save(update_fields=["progress"])

    def is_manager(self, user):
        if not user or not user.is_authenticated:
            return False
        return user.is_admin or user.is_project_manager or self.managers.filter(pk=user.pk).exists()

    def is_incharge(self, user):
        if not user or not user.is_authenticated:
            return False
        return user.is_admin or user.is_project_manager or self.project_incharge == user

    def save(self, *args, **kwargs):
        if not self.project_id:
            words = self.name.replace("-", " ").split()
            initials = "".join([w[0].upper() for w in words if w and w[0].isalpha()])
            if not initials:
                initials = "".join(random.choices(string.ascii_uppercase, k=3))

            year = timezone.now().year
            count = Project.objects.filter(created_at__year=year).count() + 1
            if self.pk:
                count = Project.objects.filter(
                    created_at__year=self.created_at.year
                ).count()

            while True:
                pid = f"PRJ-{initials}-{year}-{count:04d}"
                if not Project.objects.filter(project_id=pid).exists():
                    self.project_id = pid
                    break
                count += 1
        super().save(*args, **kwargs)


class ProjectModule(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="modules"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class ModuleMember(models.Model):
    ROLE_CHOICES = [
        ("designer", "Designer"),
        ("developer", "Developer"),
        ("tester", "Tester"),
    ]
    module = models.ForeignKey(
        ProjectModule, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="module_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="developer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("module", "user")

    def __str__(self):
        return f"{self.user} ({self.get_role_display()}) in {self.module.name}"


class Requirement(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("review", "In Review"),
        ("approved", "Approved"),
        ("implemented", "Implemented"),
        ("verified", "Verified"),
        ("deferred", "Deferred"),
        ("deprecated", "Deprecated"),
    ]
    TYPE_CHOICES = [
        ("business", "Business Requirement (BRD)"),
        ("functional", "Functional Requirement (FRD)"),
        ("technical", "Technical Requirement (TRD)"),
        ("uiux", "UI/UX Requirement"),
        ("security", "Security Requirement"),
        ("api", "API Requirement"),
        ("database", "Database Requirement"),
        ("non_functional", "Non-Functional Requirement"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="requirements"
    )
    module = models.ForeignKey(
        "ProjectModule",
        on_delete=models.SET_NULL,
        related_name="requirements",
        null=True,
        blank=True,
    )
    req_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    requirement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="functional")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    assigned_team = models.CharField(max_length=200, blank=True, null=True)
    dependencies = models.ManyToManyField("self", blank=True, symmetrical=False, related_name="dependent_on")
    version = models.PositiveIntegerField(default=1)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_requirements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Approval and Trash fields
    is_approved = models.BooleanField(default=False)
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_requirements",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.req_id}] {self.name}" if self.req_id else self.name

    @property
    def progress(self):
        tasks = self.tasks.all()
        total = tasks.count()
        if total == 0:
            return 0
        done = tasks.filter(status="done").count()
        return int((done / total) * 100)

    def save(self, *args, **kwargs):
        if not self.req_id and self.project:
            if self.project.project_id and len(self.project.project_id.split("-")) > 1:
                project_prefix = self.project.project_id.split("-")[1]
            elif self.project.project_id:
                project_prefix = self.project.project_id.split("-")[0]
            else:
                project_prefix = "PROJ"
            year = timezone.now().year
            count = Requirement.objects.filter(project=self.project).count() + 1
            while True:
                rid = f"REQ-{project_prefix}-{year}-{count:04d}"
                if not Requirement.objects.filter(req_id=rid).exists():
                    self.req_id = rid
                    break
                count += 1
        super().save(*args, **kwargs)


class Task(models.Model):
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("review", "In Review"),
        ("done", "Done"),
        ("blocked", "Blocked"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    TYPE_CHOICES = [
        ("task", "Task"),
        ("bug", "Bug"),
        ("feature", "Feature"),
        ("improvement", "Improvement"),
        ("research", "Research"),
    ]

    task_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True,
    )
    module = models.ForeignKey(
        "ProjectModule",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )
    release = models.ForeignKey(
        "Release",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="task")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_tasks"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    parent_task = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subtasks",
    )
    sprint = models.ForeignKey(
        "Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    milestone = models.CharField(max_length=200, blank=True, null=True)
    story_points = models.PositiveIntegerField(default=0, blank=True)
    due_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    actual_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    
    tags = models.CharField(
        max_length=500, blank=True, help_text="Comma-separated tags"
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Approval and Trash fields
    is_approved = models.BooleanField(default=False)
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_tasks",
    )

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"[{self.task_id}] {self.title}" if self.task_id else self.title

    @property
    def is_overdue(self):
        if self.due_date and self.status != "done":
            return self.due_date < timezone.now().date()
        return False

    @property
    def active_bugs(self):
        return self.linked_bugs.filter(is_in_trash=False)

    @property
    def tag_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(",") if t.strip()]
        return []

    @property
    def test_case_stats(self):
        active_tcs = self.test_cases.filter(is_in_trash=False)
        total = active_tcs.count()
        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "pending": 0,
                "retest": 0,
                "percentage": 0,
            }
        passed = active_tcs.filter(status="passed").count()
        failed = active_tcs.filter(status="failed").count()
        pending = active_tcs.filter(status="pending").count()
        retest = active_tcs.filter(status="retest").count()
        percentage = int((passed / total) * 100)
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "retest": retest,
            "percentage": percentage,
        }

    @property
    def can_complete(self):
        active_tcs = self.test_cases.filter(is_in_trash=False)
        if not active_tcs.exists():
            return True
        # Only when all test cases are passed can the task be closed.
        return active_tcs.filter(status="passed").count() == active_tcs.count()

    def save(self, *args, **kwargs):
        if self.status == "done" and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != "done":
            self.completed_at = None

        if not self.task_id:
            type_map = {
                "task": "TAS",
                "bug": "BUG",
                "feature": "FEA",
                "improvement": "IMP",
                "research": "RES",
            }
            type_prefix = type_map.get(self.task_type, "TAS")

            project_prefix = "GEN"
            if self.project:
                project_prefix = (
                    self.project.project_id.split("-")[1]
                    if self.project.project_id and len(self.project.project_id.split("-")) > 1
                    else (self.project.project_id.split("-")[0] if self.project.project_id else "PROJ")
                )

            year = timezone.now().year
            module_num = f"{self.module.pk:04d}" if self.module else "0000"

            # Count tasks for this project in this year
            if self.project:
                count = Task.objects.filter(project=self.project).count() + 1
            else:
                count = Task.objects.filter(project__isnull=True).count() + 1

            while True:
                tid = f"{type_prefix}-{project_prefix}-{year}-{count:04d}"
                if not Task.objects.filter(task_id=tid).exists():
                    self.task_id = tid
                    break
                count += 1

        super().save(*args, **kwargs)
        # Update project progress
        if self.project and not getattr(self, '_skip_progress_update', False):
            self.project.update_progress()


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(upload_to="comments/%Y/%m/", null=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"


# ── Cross-app re-exports (backward compatibility) ─────────────────────────────
# These allow `from tasks.models import X` to keep working in legacy call sites.
from notifications.models import Notification  # noqa: F401, E402
from bugs.models import BugReport, BugComment  # noqa: F401, E402
from events.models import CalendarEvent, UserCalendarSettings  # noqa: F401, E402
from notes.models import KnowledgeBaseNote  # noqa: F401, E402

class SystemSettings(models.Model):
    primary_color = models.CharField(max_length=7, default="#4f8ef7")
    font_size = models.CharField(max_length=20, default="14px")
    default_pm_password = models.CharField(max_length=128, default="nexuspm123")

    class Meta:
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SystemIssue(models.Model):
    TYPE_CHOICES = [
        ("bug", "Bug"),
        ("feature", "Feature Request"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    title = models.CharField(max_length=300)
    description = models.TextField()
    issue_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="bug")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_system_issues",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_system_issues",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_issue_type_display()}: {self.title}"


class PipelineRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("passed", "Passed"),
        ("failed", "Failed"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="pipeline_runs"
    )
    name = models.CharField(max_length=200, help_text="e.g. Build & Test")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    trigger_commit = models.CharField(
        max_length=100, blank=True, help_text="Git commit hash"
    )
    triggered_by = models.CharField(
        max_length=100, blank=True, help_text="User or webhook name"
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.name} - {self.get_status_display()} ({self.project.name})"


class Release(models.Model):
    TYPE_CHOICES = [
        ("partial", "Partial (Minor/Nightly)"),
        ("phase", "Phase (Major)"),
    ]
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="releases"
    )
    name = models.CharField(max_length=200, help_text="e.g. May 2025 Release")
    release_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="partial"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    description = models.TextField(
        blank=True, help_text="Release notes (Markdown supported)"
    )
    tag_name = models.CharField(max_length=50, blank=True, help_text="e.g. v1.0.0")
    target_date = models.DateField(null=True, blank=True)
    release_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    is_approved = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    is_prerelease = models.BooleanField(default=False)
    version = models.CharField(max_length=50, blank=True, help_text="e.g. 1.0.0")
    
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="published_releases")
    
    # Audit & Security
    checksum = models.CharField(max_length=255, blank=True, null=True) # Overall release bundle checksum
    metadata = models.JSONField(default=dict, blank=True)
    
    @property
    def is_locked(self):
        return self.status == 'completed'


    class Meta:
        ordering = ["-release_date"]
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            old_instance = Release.objects.get(pk=self.pk)
            if old_instance.is_locked:
                raise ValidationError("This release is locked and cannot be modified.")
        super().save(*args, **kwargs)


def release_file_upload_to(instance, filename):
    """
    Store release files in an immutable structure: releases/<version>/<path>/<filename>
    """
    version_str = instance.release.version or instance.release.tag_name or f"release_{instance.release.pk}"
    # Clean version string
    version_str = "".join(c for c in version_str if c.isalnum() or c in ('.', '-', '_')).strip()
    return os.path.join("releases", version_str, filename)

class ReleaseFile(models.Model):
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, related_name="release_files"
    )
    # Source file (optional, might be deleted)
    project_file = models.ForeignKey(
        "files.ProjectFile", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="release_mappings"
    )
    
    # THE SNAPSHOT: The actual frozen copy of the file
    file = models.FileField(upload_to=release_file_upload_to, max_length=500, null=True)
    
    # Metadata snapshot (frozen at time of release)
    original_name = models.CharField(max_length=300, default="")
    relative_path = models.CharField(max_length=500, blank=True, default="") # e.g. "Docs/Subfolder/file.pdf"
    file_size = models.PositiveBigIntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True, default="")
    content_hash = models.CharField(max_length=128, blank=True, null=True) # SHA-256
    
    is_extra_asset = models.BooleanField(default=False) # True if uploaded directly to release (not snapshotted from project)
    version = models.PositiveSmallIntegerField(default=1) # The version of the project file when snapshotted
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Release Asset"
        verbose_name_plural = "Release Assets"

    def __str__(self):
        return f"{self.original_name} in {self.release.name}"

    def get_project_relative_path(self):
        if self.is_extra_asset:
            return os.path.join("assets", self.original_name)
        return self.relative_path or self.original_name

    @property
    def icon_class(self):
        # Mirroring ProjectFile icon logic
        ext = os.path.splitext(self.original_name)[1].lower()
        from files.models import ProjectFile
        ft = ProjectFile.detect_file_type(ext)
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
        }.get(ft, "fa-file")

    @property
    def icon_color(self):
        ext = os.path.splitext(self.original_name)[1].lower()
        from files.models import ProjectFile
        ft = ProjectFile.detect_file_type(ext)
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
        }.get(ft, "#7a8aaa")

    @property
    def file_size_display(self):
        size = self.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024**2:
            return f"{size / 1024:.1f} KB"
        elif size < 1024**3:
            return f"{size / 1024**2:.1f} MB"
        return f"{size / 1024**3:.1f} GB"


class ReleaseModuleVersion(models.Model):
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, related_name="module_versions"
    )
    module = models.ForeignKey(
        "ProjectModule", on_delete=models.CASCADE, related_name="release_versions"
    )
    version_string = models.CharField(max_length=50, blank=True)
    file = models.ForeignKey(
        "files.ProjectFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        unique_together = ("release", "module")

    def __str__(self):
        return f"{self.module.name} ({self.version_string}) for {self.release.name}"


class ReleaseDeletionRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="deletion_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_requests")
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']


class ProjectDeletionRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="deletion_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_project_requests")
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Deletion request for {self.project.name} by {self.requested_by}"


class ReleaseLog(models.Model):
    ACTION_CHOICES = (
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('published', 'Published'),
        ('snapshot_created', 'Snapshot Created'),
        ('asset_uploaded', 'Asset Uploaded'),
        ('deletion_requested', 'Deletion Requested'),
        ('deletion_approved', 'Deletion Approved'),
        ('deletion_rejected', 'Deletion Rejected'),
        ('restored', 'Restored'),
    )
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class ModuleForumPost(models.Model):
    module = models.ForeignKey(
        ProjectModule, on_delete=models.CASCADE, related_name="forum_posts"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(upload_to="forum_posts/%Y/%m/", null=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Post by {self.author} in {self.module.name}"


from testcases.models import TestCase, TestCaseAttachment, TestCaseHistory  # noqa: F401, E402


class Sprint(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sprints")
    name = models.CharField(max_length=200)
    goal = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class AuditLog(models.Model):
    MODULE_CHOICES = [
        ("project", "Project"),
        ("requirement", "Requirement"),
        ("task", "Task"),
        ("test_case", "Test Case"),
        ("bug", "Bug Report"),
        ("release", "Release"),
        ("user", "User Management"),
        ("system", "System Settings"),
        ("file", "File"),
        ("folder", "Folder"),
    ]
    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("publish", "Publish"),
        ("restore", "Restore"),
        ("upload", "Upload"),
        ("download", "Download"),
        ("move", "Move"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_logs")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    entity_id = models.CharField(max_length=100, blank=True, null=True)
    entity_name = models.CharField(max_length=255, blank=True, null=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} - {self.action_type} - {self.module} at {self.timestamp}"


class RequirementVersion(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    change_log = models.TextField(blank=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = ("requirement", "version_number")

    def __str__(self):
        return f"{self.requirement.req_id} - v{self.version_number}"


class RequirementComment(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(upload_to="requirements/comments/%Y/%m/", null=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.requirement}"



