from django.contrib import admin
from django.utils.html import format_html
from .models import FileCategory, FileComment, ProjectFile, SystemSettings, DocumentAccessRight


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ["max_file_size_gb"]


@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = [
        "original_name",
        "type_badge",
        "file_size_display",
        "project",
        "task",
        "uploaded_by",
        "is_in_trash",
        "created_at",
    ]
    list_filter = [
        "file_type", 
        "project", 
        "uploaded_by", 
        "is_in_trash", 
        "is_public", 
        "extension", 
        "created_at"
    ]
    search_fields = ["original_name", "title", "description", "extension"]
    raw_id_fields = ["project", "task", "uploaded_by", "category", "parent_file"]
    date_hierarchy = "created_at"
    list_per_page = 25

    @admin.display(description="Type")
    def type_badge(self, obj):
        colors = {
            "image": "#06b6d4",
            "pdf": "#ef4444",
            "document": "#6366f1",
            "spreadsheet": "#22c55e",
            "presentation": "#f97316",
            "code": "#a855f7",
            "archive": "#f59e0b",
            "video": "#ef4444",
            "audio": "#22c55e",
            "cad": "#64748b",
            "other": "#6b7280",
        }
        color = colors.get(obj.file_type, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            color,
            obj.get_file_type_display(),
        )

    @admin.display(description="Size")
    def file_size_display(self, obj):
        try:
            return obj.file_size_display
        except Exception:
            return f"{obj.file_size} bytes"


@admin.register(FileCategory)
class FileCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "parent", "created_by", "created_at"]
    list_filter = ["project", "created_by"]
    search_fields = ["name"]


@admin.register(FileComment)
class FileCommentAdmin(admin.ModelAdmin):
    list_display = ["file", "author", "content_preview", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content", "author__username", "file__original_name"]
    raw_id_fields = ["file", "author"]

    @admin.display(description="Comment")
    def content_preview(self, obj):
        return obj.content[:60] + "..." if len(obj.content) > 60 else obj.content


@admin.register(DocumentAccessRight)
class DocumentAccessRightAdmin(admin.ModelAdmin):
    list_display = ["user", "file", "kb_note", "can_view", "can_edit", "can_delete"]
    list_filter = ["can_view", "can_edit", "can_delete"]
    search_fields = ["user__username", "file__original_name", "kb_note__title"]
    raw_id_fields = ["user", "file", "kb_note"]
