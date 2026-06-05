from django.contrib import admin
from .models import BugReport, BugComment

"""
This module registers Bug models with the Django Admin panel,
defining list columns, sidebar search filters, and matching query parameters.
"""

@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    """Admin configuration settings for the BugReport model."""
    list_display = ["title", "project", "reported_by", "severity", "status", "created_at"]
    list_filter = ["severity", "status", "project"]
    search_fields = ["title", "description"]


@admin.register(BugComment)
class BugCommentAdmin(admin.ModelAdmin):
    """Admin configuration settings for the BugComment model."""
    list_display = ["bug", "author", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content"]
