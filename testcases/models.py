from django.conf import settings
from django.db import models
from django.utils import timezone


class TestCase(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("blocked", "Blocked"),
        ("retest", "Needs Re-test"),
    ]

    test_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    project = models.ForeignKey(
        "tasks.Project", on_delete=models.CASCADE, related_name="test_cases"
    )
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="test_cases")
    title = models.CharField(max_length=300)
    scenario = models.TextField(blank=True)
    preconditions = models.TextField(blank=True)
    steps = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    actual_result = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    assigned_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_test_cases"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_test_cases",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_test_cases",
    )
    verified_date = models.DateTimeField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Trash tracking fields
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_test_cases",
    )

    class Meta:
        db_table = "tasks_testcase"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.test_id}] {self.title}" if self.test_id else self.title

    def save(self, *args, **kwargs):
        if not self.test_id and self.project:
            project_prefix = (
                self.project.project_id.split("-")[0]
                if self.project.project_id
                else "PROJ"
            )
            year = timezone.now().year
            count = TestCase.objects.filter(project=self.project).count() + 1
            while True:
                tid = f"{project_prefix}-TC-{year}-{count:06d}"
                if not TestCase.objects.filter(test_id=tid).exists():
                    self.test_id = tid
                    break
                count += 1
        super().save(*args, **kwargs)


class TestCaseAttachment(models.Model):
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="test_cases/attachments/%Y/%m/")
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_testcaseattachment"


class TestCaseHistory(models.Model):
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="history"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_testcasehistory"
        ordering = ["-timestamp"]


class TestCaseComment(models.Model):
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(upload_to="test_cases/comments/%Y/%m/", null=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tasks_testcasecomment"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.test_case}"
