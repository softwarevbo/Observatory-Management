from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("project_manager", "Project Manager"),
        ("member", "Member"),
        ("student", "Student"),
    ]

    MODULE_CHOICES = [
        ("electronics", "Electronics"),
        ("mechanical", "Mechanical"),
        ("optics", "Optics"),
        ("simulation", "Simulation"),
        ("software", "Software"),
        ("general", "General"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    team = models.CharField(max_length=20, choices=MODULE_CHOICES, default="general")
    avatar_color = models.CharField(max_length=7, default="#6366f1")
    profile_picture = models.ImageField(upload_to="avatars/", null=True, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    theme_preference = models.CharField(max_length=20, default="light")
    email_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Access Flags
    can_access_pm = models.BooleanField(default=True)
    can_access_inventory = models.BooleanField(default=False)
    can_access_telescope = models.BooleanField(default=False)
    is_telescope_admin = models.BooleanField(default=False)

    # Telescope Specific Permissions
    can_operate_vbt = models.BooleanField(default=True)
    can_operate_jcbt = models.BooleanField(default=True)
    can_operate_zeiss = models.BooleanField(default=True)
    can_operate_cassegrain = models.BooleanField(default=True)
    can_operate_schmidt = models.BooleanField(default=True)
    can_command_dome = models.BooleanField(default=True)
    can_trigger_exposures = models.BooleanField(default=True)

    # Inventory Permissions Compatibility
    inventory_branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pm_users",
    )
    can_access_adjustments_page = models.BooleanField(default=True)
    can_manage_adjustments = models.BooleanField(default=True)
    can_access_serials_page = models.BooleanField(default=True)
    can_manage_serials = models.BooleanField(default=True)
    can_access_limits_page = models.BooleanField(default=True)
    can_manage_limits = models.BooleanField(default=True)
    can_access_alerts_page = models.BooleanField(default=True)
    can_manage_alerts = models.BooleanField(default=True)
    can_access_rentals_page = models.BooleanField(default=True)
    can_manage_rentals = models.BooleanField(default=True)
    can_access_shortage_page = models.BooleanField(default=True)
    can_manage_shortage_exports = models.BooleanField(default=True)
    can_view_all_branches_inventory = models.BooleanField(default=True)
    can_add_inventory = models.BooleanField(default=True)
    can_edit_inventory = models.BooleanField(default=True)
    can_delete_inventory = models.BooleanField(default=True)
    can_approve_transfer = models.BooleanField(default=True)
    can_export_reports = models.BooleanField(default=True)
    can_manage_users = models.BooleanField(default=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == "admin" or self.is_superuser

    @property
    def is_project_manager(self):
        return self.role == "project_manager"

    @property
    def is_student(self):
        return self.role == "student"

    @property
    def is_super_admin(self):
        return self.role == "admin" or self.is_superuser

    @property
    def is_branch_admin(self):
        return self.role == "admin" or self.is_superuser

    @property
    def branch(self):
        return self.inventory_branch

    @property
    def display_name(self):
        if self.nickname:
            return self.nickname
        return self.get_full_name() or self.username

    @property
    def initials(self):
        name = self.get_full_name()
        if name:
            parts = name.split()
            return "".join(p[0].upper() for p in parts[:2])
        return self.username[:2].upper()
