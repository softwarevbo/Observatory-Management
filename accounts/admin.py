from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User

# ─── Custom Actions ───────────────────────────────────────────────────────────


@admin.action(description="🔴 Set selected users → Admin")
def make_admin(modeladmin, request, queryset):
    updated = queryset.exclude(pk=request.user.pk).update(role="admin")
    messages.success(request, f"✅ {updated} user(s) set to Admin.")


@admin.action(description="🟡 Set selected users → Project Manager")
def make_project_manager(modeladmin, request, queryset):
    updated = queryset.exclude(pk=request.user.pk).update(role="project_manager")
    messages.success(request, f"✅ {updated} user(s) set to Project Manager.")


@admin.action(description="🟢 Set selected users → Member")
def make_member(modeladmin, request, queryset):
    updated = queryset.exclude(pk=request.user.pk).update(role="member")
    messages.success(request, f"✅ {updated} user(s) set to Member.")


@admin.action(description="✅ Activate selected users")
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    messages.success(request, f"✅ {updated} user(s) activated.")


@admin.action(description="❌ Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
    messages.success(request, f"✅ {updated} user(s) deactivated.")


# ─── User Admin ───────────────────────────────────────────────────────────────


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "full_name",
        "email",
        "role_badge",
        "team",
        "designation",
        "status_badge",
        "is_superuser_badge",
        "date_joined",
    ]
    list_filter = ["role", "team", "is_active", "is_superuser", "is_staff"]
    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "designation",
        "phone",
    ]
    ordering = ["-date_joined"]
    list_per_page = 25
    date_hierarchy = "date_joined"
    actions = [
        make_admin,
        make_project_manager,
        make_member,
        activate_users,
        deactivate_users,
    ]

    fieldsets = (
        (
            _("Login Credentials"),
            {
                "fields": ("username", "password"),
            },
        ),
        (
            _("Personal Info"),
            {
                "fields": ("first_name", "last_name", "email", "designation", "phone"),
            },
        ),
        (
            _("Role & Team"),
            {
                "fields": ("role", "team", "avatar_color"),
                "classes": ("wide",),
                "description": "Changing role here overrides the project-level role. Use bulk actions above to change multiple users at once.",
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Important Dates"),
            {
                "fields": ("last_login", "date_joined"),
                "classes": ("collapse",),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "team",
                    "designation",
                    "phone",
                    "is_active",
                ),
            },
        ),
    )

    readonly_fields = ["date_joined", "last_login"]

    @admin.display(description="Full Name", ordering="first_name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Role")
    def role_badge(self, obj):
        colors = {
            "admin": ("#ef4444", "Admin"),
            "project_manager": ("#f59e0b", "Project Manager"),
            "member": ("#22c55e", "Member"),
        }
        color, label = colors.get(obj.role, ("#6b7280", obj.role))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color:#22c55e;font-weight:600;">✅ Active</span>'
            )
        return format_html(
            '<span style="color:#ef4444;font-weight:600;">❌ Inactive</span>'
        )

    @admin.display(description="Superuser")
    def is_superuser_badge(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span style="color:#a855f7;font-weight:600;">⭐ Yes</span>'
            )
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(is_superuser=False)
        return qs

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj and obj.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj == request.user:
            return False
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
