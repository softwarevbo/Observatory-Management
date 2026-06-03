from django.contrib import admin
from .models import TestCase, TestCaseAttachment, TestCaseHistory


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ["test_id", "title", "project", "task", "priority", "status", "approval_status"]
    list_filter = ["priority", "status", "approval_status", "project"]
    search_fields = ["test_id", "title", "scenario"]


@admin.register(TestCaseAttachment)
class TestCaseAttachmentAdmin(admin.ModelAdmin):
    list_display = ["test_case", "file", "uploaded_at"]


@admin.register(TestCaseHistory)
class TestCaseHistoryAdmin(admin.ModelAdmin):
    list_display = ["test_case", "user", "action", "timestamp"]
