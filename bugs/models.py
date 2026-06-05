from django.conf import settings
from django.db import models

"""
This module defines the database models for the Bug Tracking system.
It contains:
1. BugReport: Represents a logged software bug or hardware issue, tracking its project context,
   reporter, severity, steps to reproduce, actual vs expected outcomes, resolution metrics,
   and trash/deletion states.
2. BugComment: Enables interactive thread comments and attachment uploads on bug reports.
"""

class BugReport(models.Model):
    """
    Model representing a single Bug Report entry.
    Tracks details of issues, assignments, related tasks, status updates, and soft-delete states.
    """
    # Severity choices representing severity impact levels of reported bugs
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    # Status choices representing active states throughout a bug's lifecycle
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("wont_fix", "Won't Fix"),
    ]

    # Core identification fields
    title = models.CharField(max_length=300)
    description = models.TextField()
    
    # Links bug report to a Project within the task management system
    project = models.ForeignKey(
        "tasks.Project",
        on_delete=models.CASCADE,
        related_name="bug_reports",
        null=True,
        blank=True,
    )
    
    # Records who submitted the bug report
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reported_bugs"
    )
    
    # Assigns one or more team members to resolve the bug
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_bugs"
    )
    
    # Severity and status controls
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    
    # Diagnostic fields
    steps_to_reproduce = models.TextField(blank=True)
    expected_behavior = models.TextField(blank=True)
    actual_behavior = models.TextField(blank=True)
    
    # Links bug to a companion PM Task for tracking development progress
    linked_task = models.ForeignKey(
        "tasks.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_bugs"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete variables (standard practice instead of destructive hard deletes)
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bugs",
    )

    # Resolution Tracking Logic
    resolution_summary = models.TextField(blank=True)
    solving_results = models.TextField(blank=True)
    
    # FileField to upload patch details, logs, screenshots or code edits.
    # Upload path organizes files into nested directories based on year and month.
    resolution_attachment = models.FileField(
        upload_to="bugs/resolutions/%Y/%m/", null=True, blank=True
    )
    resolution_date = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_bugs",
    )

    class Meta:
        """
        Meta configurations.
        db_table overrides default table name to retain compatibility with legacy tables.
        """
        db_table = "tasks_bugreport"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class BugComment(models.Model):
    """
    Model representing a text comment left on a specific Bug Report.
    Supports nested comment replies and file attachments.
    """
    # Parent bug report
    bug = models.ForeignKey(BugReport, on_delete=models.CASCADE, related_name="comments")
    
    # Comment author
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    
    # Uploaded image/file attached to the comment
    attachment = models.FileField(
        upload_to="bugs/comments/%Y/%m/", null=True, blank=True
    )
    
    # Self-referencing foreign key to support nested comment reply threads (e.g. replies on comments)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_bugcomment"
        ordering = ["created_at"] # Oldest comments display first in thread

    def __str__(self):
        return f"Comment by {self.author} on {self.bug.title}"
