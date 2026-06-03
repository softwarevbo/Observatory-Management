from django.contrib import admin
from .models import BugReport, BugComment


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "reported_by", "severity", "status", "created_at"]
    list_filter = ["severity", "status", "project"]
    search_fields = ["title", "description"]


@admin.register(BugComment)
class BugCommentAdmin(admin.ModelAdmin):
    list_display = ["bug", "author", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content"]
