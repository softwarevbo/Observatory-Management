from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User

"""
This module customizes the Django Administrative Interface (django-admin) for the custom User model.
It defines:
1. Custom admin actions (bulk status updates, role changes)
2. Custom fields rendering (badges with CSS style styling)
3. Granular permissions logic (restricting non-superusers from modifying superusers)
4. Collapsible and organized fieldsets for the user detail pages
"""

# ─── Custom Admin Actions ───────────────────────────────────────────────────────────
# Custom actions allow administrators to select multiple records in the list view 
# and perform bulk operations on them at once.

@admin.action(description="🔴 Set selected users → Admin")
def make_admin(modeladmin, request, queryset):
    """
    Bulk action to change the role of selected users to 'admin'.
    Excludes the current logged-in user to prevent self-role modification.
    """
    updated = queryset.exclude(pk=request.user.pk).update(role="admin")
    messages.success(request, f"✅ {updated} user(s) set to Admin.")


@admin.action(description="🟡 Set selected users → Project Manager")
def make_project_manager(modeladmin, request, queryset):
    """
    Bulk action to change the role of selected users to 'project_manager'.
    Excludes the current logged-in user to prevent self-role modification.
    """
    updated = queryset.exclude(pk=request.user.pk).update(role="project_manager")
    messages.success(request, f"✅ {updated} user(s) set to Project Manager.")


@admin.action(description="🟢 Set selected users → Member")
def make_member(modeladmin, request, queryset):
    """
    Bulk action to change the role of selected users to 'member'.
    Excludes the current logged-in user to prevent self-role modification.
    """
    updated = queryset.exclude(pk=request.user.pk).update(role="member")
    messages.success(request, f"✅ {updated} user(s) set to Member.")


@admin.action(description="✅ Activate selected users")
def activate_users(modeladmin, request, queryset):
    """
    Bulk action to activate user accounts, setting `is_active=True`.
    """
    updated = queryset.update(is_active=True)
    messages.success(request, f"✅ {updated} user(s) activated.")


@admin.action(description="❌ Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    """
    Bulk action to deactivate user accounts, setting `is_active=False`.
    Excludes the current logged-in user to prevent self-deactivation.
    """
    updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
    messages.success(request, f"✅ {updated} user(s) deactivated.")


# ─── User Admin Customization ─────────────────────────────────────────────────────────

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin extending Django's BaseUserAdmin.
    
    Since we extended AbstractUser, we need to adapt Django's standard UserAdmin forms,
    fieldsets, actions, and list layout to include our custom attributes.
    """
    
    # Fields to display in the main list table of the admin panel
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
    
    # Sidebar filter options
    list_filter = ["role", "team", "is_active", "is_superuser", "is_staff"]
    
    # Search input fields
    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "designation",
        "phone",
    ]
    
    # Default order of listing records (newest users first)
    ordering = ["-date_joined"]
    
    # Pagination: limit to 25 users per page
    list_per_page = 25
    
    # Add a date-based navigation bar on top (e.g. Filter by year, month, day)
    date_hierarchy = "date_joined"
    
    # Register the custom bulk actions defined above
    actions = [
        make_admin,
        make_project_manager,
        make_member,
        activate_users,
        deactivate_users,
    ]

    # Fieldsets define how the user editing detail page is laid out and structured into sections.
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
                "classes": ("collapse",), # Section can be collapsed/hidden dynamically
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

    # Fieldsets layout displayed when adding a new user through the admin panel.
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

    # Prevent modification of timestamps directly (they are read-only)
    readonly_fields = ["date_joined", "last_login"]

    # ─── Custom Calculated Admin Fields (badges) ───────────────────────────────────

    @admin.display(description="Full Name", ordering="first_name")
    def full_name(self, obj):
        """Calculates and returns the user's full name, falling back to a dash if empty."""
        return obj.get_full_name() or "—"

    @admin.display(description="Role")
    def role_badge(self, obj):
        """
        Renders a beautifully styled HTML badge representing the user's role.
        Using `format_html` ensures the tags are rendered safely as HTML without escaping.
        """
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
        """Renders the status (Active/Inactive) as a color-coded HTML text."""
        if obj.is_active:
            return format_html(
                '<span style="color:#22c55e;font-weight:600;">{}</span>',
                "✅ Active"
            )
        return format_html(
            '<span style="color:#ef4444;font-weight:600;">{}</span>',
            "❌ Inactive"
        )

    @admin.display(description="Superuser")
    def is_superuser_badge(self, obj):
        """Displays a purple star badge for superusers, otherwise empty."""
        if obj.is_superuser:
            return format_html(
                '<span style="color:#a855f7;font-weight:600;">{}</span>',
                "⭐ Yes"
            )
        return "—"

    # ─── Custom Permission Overrides ──────────────────────────────────────────────
    # The following hooks enforce security logic. For example, standard admins 
    # cannot view or edit superusers in the list.

    def get_queryset(self, request):
        """
        Overrides the list query.
        If the logged-in user is NOT a superuser, filter out superusers from the list.
        """
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(is_superuser=False)
        return qs

    def has_change_permission(self, request, obj=None):
        """
        Determines if a user has change permissions for a specific object.
        Non-superusers are blocked from editing superusers.
        """
        if request.user.is_superuser:
            return True
        if obj and obj.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """
        Determines if a user can delete a specific user account.
        - Users cannot delete their own account.
        - Non-superusers cannot delete superusers.
        """
        if obj and obj == request.user:
            return False
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
