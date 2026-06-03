from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Project, ProjectModule, ModuleMember, Requirement, Task, Comment, 
    SystemSettings, SystemIssue, PipelineRun, Release, ReleaseFile,
    ReleaseModuleVersion, ReleaseDeletionRequest, ReleaseLog,
    ModuleForumPost,
    Sprint, AuditLog, RequirementVersion
)

# ─── Actions ─────────────────────────────────────────────────────────────────


@admin.action(description="Mark selected tasks as Done")
def mark_tasks_done(modeladmin, request, queryset):
    updated = queryset.update(status="done")
    messages.success(request, f"✅ {updated} task(s) marked as Done.")


@admin.action(description="Mark selected projects as Active")
def mark_projects_active(modeladmin, request, queryset):
    updated = queryset.update(status="active")
    messages.success(request, f"✅ {updated} project(s) set to Active.")





# ─── Project Admin ────────────────────────────────────────────────────────────


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "module",
        "status_badge",
        "priority_badge",
        "progress_bar",
        "get_managers",
        "member_count",
        "start_date",
        "end_date",
    ]
    list_filter = ["module", "status", "priority", "start_date", "end_date"]
    search_fields = ["name", "description"]
    filter_horizontal = ["members", "managers"]
    date_hierarchy = "start_date"
    actions = [mark_projects_active]
    list_per_page = 20

    @admin.display(description="Managers")
    def get_managers(self, obj):
        return ", ".join([user.username for user in obj.managers.all()])

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "active": "#22c55e",
            "completed": "#6366f1",
            "on_hold": "#f59e0b",
            "cancelled": "#ef4444",
            "planning": "#06b6d4",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Priority")
    def priority_badge(self, obj):
        colors = {
            "critical": "#ef4444",
            "high": "#f97316",
            "medium": "#f59e0b",
            "low": "#22c55e",
        }
        color = colors.get(obj.priority, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    @admin.display(description="Progress")
    def progress_bar(self, obj):
        p = obj.progress or 0
        color = "#22c55e" if p >= 75 else "#f59e0b" if p >= 40 else "#ef4444"
        return format_html(
            '<div style="background:#1e293b;border-radius:4px;height:8px;width:80px;">'
            '<div style="background:{};border-radius:4px;height:8px;width:{}%;"></div>'
            "</div> {}%",
            color,
            min(p, 100),
            p,
        )

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()


# ─── Task Admin ───────────────────────────────────────────────────────────────


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "project",
        "task_type",
        "status_badge",
        "priority_badge",
        "get_assignees",
        "due_date",
        "is_overdue_badge",
    ]
    list_filter = ["status", "priority", "task_type", "project", "created_by", "is_in_trash", "due_date"]
    search_fields = ["title", "description"]
    raw_id_fields = ["project", "created_by"]
    filter_horizontal = ["assignees"]
    date_hierarchy = "created_at"
    actions = [mark_tasks_done]
    list_per_page = 25

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "todo": "#6b7280",
            "in_progress": "#3b82f6",
            "review": "#a855f7",
            "done": "#22c55e",
            "cancelled": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Priority")
    def priority_badge(self, obj):
        colors = {
            "critical": "#ef4444",
            "high": "#f97316",
            "medium": "#f59e0b",
            "low": "#22c55e",
        }
        color = colors.get(obj.priority, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    @admin.display(description="Overdue", boolean=True)
    def is_overdue_badge(self, obj):
        return obj.is_overdue

    @admin.display(description="Assignees")
    def get_assignees(self, obj):
        return ", ".join([user.username for user in obj.assignees.all()])


# ─── Comment Admin ────────────────────────────────────────────────────────────


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["task", "author", "content_preview", "created_at"]
    raw_id_fields = ["task", "author"]
    search_fields = ["content", "author__username", "task__title"]
    list_per_page = 30

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:60] + "..." if len(obj.content) > 60 else obj.content





# ─── Sprint Admin ─────────────────────────────────────────────────────────────

@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "start_date", "end_date", "is_active", "is_completed"]
    list_filter = ["is_active", "is_completed", "project"]
    search_fields = ["name", "goal"]
    date_hierarchy = "start_date"

# ─── Requirement Admin ────────────────────────────────────────────────────────

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ["req_id", "name", "project", "priority", "status", "is_in_trash"]
    list_filter = ["status", "priority", "project", "is_in_trash"]
    search_fields = ["name", "req_id", "description"]
    list_per_page = 25

@admin.register(RequirementVersion)
class RequirementVersionAdmin(admin.ModelAdmin):
    list_display = ["requirement", "version_number", "updated_by", "updated_at"]
    list_filter = ["requirement__project", "updated_at"]
    search_fields = ["requirement__name", "description"]



# ─── Release Admin ────────────────────────────────────────────────────────────

@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ["version", "project", "status", "release_date", "is_approved"]
    list_filter = ["status", "is_approved", "project"]
    search_fields = ["version", "description"]
    date_hierarchy = "release_date"

@admin.register(ReleaseFile)
class ReleaseFileAdmin(admin.ModelAdmin):
    list_display = ["release", "original_name", "file_size", "added_at"]
    list_filter = ["release__project"]

@admin.register(ReleaseLog)
class ReleaseLogAdmin(admin.ModelAdmin):
    list_display = ["release", "action", "details", "timestamp"]
    list_filter = ["action", "release__project"]

# ─── Audit & System Admin ─────────────────────────────────────────────────────

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action_type", "module", "entity_name"]
    list_filter = ["action_type", "module", "timestamp"]
    search_fields = ["entity_name", "details", "user__username"]
    date_hierarchy = "timestamp"
    readonly_fields = ["timestamp", "user", "action_type", "module", "entity_id", "entity_name", "details", "ip_address", "user_agent"]

@admin.register(SystemIssue)
class SystemIssueAdmin(admin.ModelAdmin):
    list_display = ["title", "issue_type", "status", "created_at"]
    list_filter = ["issue_type", "status"]
    search_fields = ["title", "description"]

@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "status", "started_at", "duration_seconds"]
    list_filter = ["status", "project"]
    search_fields = ["name", "logs"]

# ─── Others ──────────────────────────────────────────────────────────────────

@admin.register(ProjectModule)
class ProjectModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "project"]
    list_filter = ["project"]
    search_fields = ["name"]

@admin.register(ModuleMember)
class ModuleMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "module", "role"]
    list_filter = ["role", "module__project"]



@admin.register(ModuleForumPost)
class ModuleForumPostAdmin(admin.ModelAdmin):
    list_display = ["author", "module", "created_at"]
    list_filter = ["module__project"]
    search_fields = ["title", "content"]

@admin.register(ReleaseDeletionRequest)
class ReleaseDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ["release", "requested_by", "status", "created_at"]
    list_filter = ["status"]

@admin.register(ReleaseModuleVersion)
class ReleaseModuleVersionAdmin(admin.ModelAdmin):
    list_display = ["release", "module", "version_string"]
    list_filter = ["release__project"]

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ["primary_color", "font_size", "default_pm_password"]


