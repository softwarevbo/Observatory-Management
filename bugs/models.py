from django.conf import settings
from django.db import models


class BugReport(models.Model):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("wont_fix", "Won't Fix"),
    ]

    title = models.CharField(max_length=300)
    description = models.TextField()
    project = models.ForeignKey(
        "tasks.Project",
        on_delete=models.CASCADE,
        related_name="bug_reports",
        null=True,
        blank=True,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reported_bugs"
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_bugs"
    )
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    steps_to_reproduce = models.TextField(blank=True)
    expected_behavior = models.TextField(blank=True)
    actual_behavior = models.TextField(blank=True)
    linked_task = models.ForeignKey(
        "tasks.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_bugs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_bugs",
    )

    # Resolution Logic
    resolution_summary = models.TextField(blank=True)
    solving_results = models.TextField(blank=True)
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
        db_table = "tasks_bugreport"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class BugComment(models.Model):
    bug = models.ForeignKey(BugReport, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(
        upload_to="bugs/comments/%Y/%m/", null=True, blank=True
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_bugcomment"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.bug.title}"
