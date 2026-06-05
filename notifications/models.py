from django.conf import settings
from django.db import models

"""
This module defines the database models for the Notifications application.
It establishes schemas for message records, links to tasks/projects, and read statuses.
"""


class Notification(models.Model):
    """
    Model representing system notifications delivered to individual users.
    Categorized by notification types, tracks target models, sender/recipient relations,
    and read status tracking.
    """
    TYPE_CHOICES = [
        ("task_assigned", "Task Assigned"),
        ("task_updated", "Task Updated"),
        ("task_completed", "Task Completed"),
        ("comment_added", "Comment Added"),
        ("due_soon", "Due Soon"),
        ("overdue", "Overdue"),
        ("project_update", "Project Update"),
        ("test_assigned", "Test Case Assigned"),
        ("test_failed", "Test Case Failed"),
        ("test_approved", "Test Case Approved"),
        ("retest_requested", "Re-test Requested"),
        ("task_ready_completion", "Task Ready for Completion"),
        ("chat_message", "New Chat Message"),
        ("bug_reported", "Bug Reported"),
        ("repo_invite", "Repository Invitation"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_notifications",
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    task = models.ForeignKey("tasks.Task", on_delete=models.SET_NULL, null=True, blank=True)
    test_case = models.ForeignKey("testcases.TestCase", on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey(
        "tasks.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_notification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} for {self.recipient}"
