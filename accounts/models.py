from django.contrib.auth.models import AbstractUser
from django.db import models

"""
This module defines the database models for the user accounts system.
It utilizes Django's built-in authentication system but extends it to support
custom fields, roles, team modules, access permissions for various applications
(Project Management, Inventory, Telescope Control), and specific user properties.
"""

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    
    By subclassing AbstractUser, we inherit standard fields like:
    - username, first_name, last_name, email, password
    - is_staff, is_active, is_superuser, last_login, date_joined
    
    We extend this model to add specific business logic properties, roles,
    teams, custom settings (like themes and email notifications), and granular 
    permissions for the IIA Observatory Management workspace (Project Management,
    Inventory management, and Telescope operations).
    """

    # Role choices defining system level admin vs module level roles.
    ROLE_CHOICES = [
        ("ROOT", "Root Administrator"),
        ("PM_ADMIN", "PM Admin"),
        ("PM_MEMBER", "PM Member"),
        ("TCS_ADMIN", "TCS Admin"),
        ("TCS_MEMBER", "TCS Member"),
        ("IM_ADMIN", "IM Admin"),
        ("IM_MEMBER", "IM Member"),
    ]

    # Module choices representing the scientific/engineering teams under IIA.
    MODULE_CHOICES = [
        ("electronics", "Electronics"),
        ("mechanical", "Mechanical"),
        ("optics", "Optics"),
        ("simulation", "Simulation"),
        ("software", "Software"),
        ("general", "General"),
    ]

    # User Profile Fields
    # role: Controls high-level permissions.
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default="member",
        help_text="Defines user level permissions."
    )
    
    # team: Identifies the technical/scientific group the user belongs to.
    team = models.CharField(
        max_length=20, 
        choices=MODULE_CHOICES, 
        default="general",
        help_text="Specifies the functional module or department team."
    )
    
    # avatar_color: Hex color code used for generating a initials-based avatar when no profile picture is set.
    avatar_color = models.CharField(
        max_length=7, 
        default="#6366f1",
        help_text="Hex code of the color theme representing the user avatar."
    )
    
    # profile_picture: Image file upload field. Uses Django's ImageField and uploads images to 'media/avatars/'.
    profile_picture = models.ImageField(
        upload_to="avatars/", 
        null=True, 
        blank=True,
        help_text="Optional profile picture image file."
    )
    
    # nickname: An optional display name chosen by the user.
    nickname = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Optional nickname or display moniker."
    )
    
    # designation: Professional job title (e.g., 'Senior Scientist', 'Project Engineer').
    designation = models.CharField(
        max_length=100, 
        blank=True,
        help_text="User's professional title/designation."
    )
    
    # phone: Primary contact number.
    phone = models.CharField(
        max_length=20, 
        blank=True,
        help_text="Contact telephone/mobile number."
    )
    
    # is_active: A flag to activate/deactivate accounts instead of deleting them (a Django best practice).
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user account is active. Deselect instead of deleting."
    )
    
    # theme_preference: Preference for dashboard colors, defaults to 'light'.
    theme_preference = models.CharField(
        max_length=20, 
        default="light",
        help_text="Dashboard UI theme preference (e.g., light, dark, night)."
    )
    
    # email_notifications: User preference to subscribe/unsubscribe to automated system email updates.
    email_notifications = models.BooleanField(
        default=True,
        help_text="Toggle to receive email updates and alerts from the system."
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Datetime when the user profile was originally created."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Datetime when the user profile was last updated."
    )

    # App Access Flags
    # These flags control general authorization access to major sub-applications.
    can_access_pm = models.BooleanField(
        default=True,
        help_text="Allows access to the Project Management System."
    )
    can_access_inventory = models.BooleanField(
        default=False,
        help_text="Allows access to the Inventory Management System."
    )
    can_access_telescope = models.BooleanField(
        default=False,
        help_text="Allows access to the Telescope Control System."
    )
    is_telescope_admin = models.BooleanField(
        default=False,
        help_text="Allows administrative configurations in the Telescope app."
    )

    # Telescope Specific Permissions
    # Granular controls over telescope systems and hardware operations.
    can_operate_vbt = models.BooleanField(
        default=True,
        help_text="Allows operation commands on the Vainu Bappu Telescope (VBT)."
    )
    can_operate_jcbt = models.BooleanField(
        default=True,
        help_text="Allows operation commands on the JC Bhattacharya Telescope (JCBT)."
    )
    can_operate_zeiss = models.BooleanField(
        default=True,
        help_text="Allows operation commands on the Zeiss Telescope."
    )
    can_operate_cassegrain = models.BooleanField(
        default=True,
        help_text="Allows operation commands on the Cassegrain Spectrograph."
    )
    can_operate_schmidt = models.BooleanField(
        default=True,
        help_text="Allows operation commands on the Schmidt Telescope."
    )
    can_command_dome = models.BooleanField(
        default=True,
        help_text="Allows opening/closing and rotation commands to the dome structure."
    )
    can_trigger_exposures = models.BooleanField(
        default=True,
        help_text="Allows triggering science CCD exposures or taking calibrations."
    )

    # Inventory Permissions Compatibility
    # Links a user to a specific physical branch/warehouse in the inventory system.
    # We reference the string 'inventory.Branch' to prevent circular import errors.
    inventory_branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pm_users",
        help_text="Associated inventory warehouse branch for stock and transfers."
    )
    
    # Granular inventory permission toggles
    can_access_adjustments_page = models.BooleanField(
        default=True,
        help_text="Allows viewing the stock adjustments list."
    )
    can_manage_adjustments = models.BooleanField(
        default=True,
        help_text="Allows creating or modifying stock adjustments."
    )
    can_access_serials_page = models.BooleanField(
        default=True,
        help_text="Allows viewing the serial tracking page."
    )
    can_manage_serials = models.BooleanField(
        default=True,
        help_text="Allows registering or editing serial/lot numbers."
    )
    can_access_limits_page = models.BooleanField(
        default=True,
        help_text="Allows viewing minimum stock thresholds/reorder limits."
    )
    can_manage_limits = models.BooleanField(
        default=True,
        help_text="Allows setting/modifying reorder points."
    )
    can_access_alerts_page = models.BooleanField(
        default=True,
        help_text="Allows viewing inventory reorder and expiry alerts."
    )
    can_manage_alerts = models.BooleanField(
        default=True,
        help_text="Allows clearing or modifying alerts configurations."
    )
    can_access_rentals_page = models.BooleanField(
        default=True,
        help_text="Allows viewing tool/item rentals."
    )
    can_manage_rentals = models.BooleanField(
        default=True,
        help_text="Allows renting out items or checking them back in."
    )
    can_access_shortage_page = models.BooleanField(
        default=True,
        help_text="Allows viewing lists of out-of-stock items."
    )
    can_manage_shortage_exports = models.BooleanField(
        default=True,
        help_text="Allows downloading Excel/CSV exports of shortage/purchase lists."
    )
    can_view_all_branches_inventory = models.BooleanField(
        default=True,
        help_text="Allows viewing stock counts across other branches."
    )
    can_add_inventory = models.BooleanField(
        default=True,
        help_text="Allows adding new stock items."
    )
    can_edit_inventory = models.BooleanField(
        default=True,
        help_text="Allows modifying details of existing stock items."
    )
    can_delete_inventory = models.BooleanField(
        default=True,
        help_text="Allows archiving/deleting stock records."
    )
    can_approve_transfer = models.BooleanField(
        default=True,
        help_text="Allows approving stock transfers between branches."
    )
    can_export_reports = models.BooleanField(
        default=True,
        help_text="Allows generating inventory stock status PDF/CSV reports."
    )
    can_manage_users = models.BooleanField(
        default=True,
        help_text="Allows administrating inventory system users."
    )

    class Meta:
        """
        Meta options for the User model.
        Defines human-readable names and default sorting behaviour.
        """
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]  # Newest users appear first by default

    def __str__(self):
        """
        String representation of a User instance.
        Used when rendering the user object in admin forms, dropdown lists, or templates.
        """
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def canonical_role(self):
        """Returns normalized canonical RBAC role string."""
        from .rbac import get_canonical_role
        return get_canonical_role(self)

    @property
    def is_root(self):
        """Checks if user is Root Administrator."""
        from .rbac import ROLE_ROOT
        return self.canonical_role == ROLE_ROOT or self.is_superuser

    @property
    def is_admin(self):
        """Checks if the user has ROOT or PM_ADMIN role or is a Django superuser."""
        from .rbac import ROLE_ROOT, ROLE_PM_ADMIN
        return self.canonical_role in [ROLE_ROOT, ROLE_PM_ADMIN] or self.is_superuser

    @property
    def is_project_manager(self):
        """Checks if the user is an admin or manages/created any project."""
        return self.is_admin or self.managed_projects.exists() or self.created_projects.exists()

    @property
    def is_student(self):
        """Checks if the user role is 'student'."""
        return self.role == "student"

    @property
    def is_super_admin(self):
        """Checks if the user is a super administrator (ROOT)."""
        return self.is_root

    @property
    def is_branch_admin(self):
        """Checks if the user has branch admin privileges."""
        from .rbac import ROLE_ROOT, ROLE_IM_ADMIN
        return self.canonical_role in [ROLE_ROOT, ROLE_IM_ADMIN] or self.is_superuser

    def save(self, *args, **kwargs):
        """Sync access flags with canonical role when saved."""
        from .rbac import (
            get_canonical_role,
            ROLE_ROOT,
            ROLE_PM_ADMIN,
            ROLE_PM_MEMBER,
            ROLE_TM_ADMIN,
            ROLE_TM_MEMBER,
            ROLE_IM_ADMIN,
            ROLE_IM_MEMBER,
        )
        c_role = get_canonical_role(self)
        if c_role:
            self.role = c_role
        if c_role == ROLE_ROOT:
            self.can_access_pm = True
            self.can_access_telescope = True
            self.can_access_inventory = True
            self.is_telescope_admin = True
        elif c_role in [ROLE_PM_ADMIN, ROLE_PM_MEMBER]:
            self.can_access_pm = True
            self.can_access_telescope = False
            self.can_access_inventory = False
            self.is_telescope_admin = False
        elif c_role in [ROLE_TM_ADMIN, ROLE_TM_MEMBER]:
            self.can_access_pm = False
            self.can_access_telescope = True
            self.can_access_inventory = False
            self.is_telescope_admin = (c_role == ROLE_TM_ADMIN)
        elif c_role in [ROLE_IM_ADMIN, ROLE_IM_MEMBER]:
            self.can_access_pm = False
            self.can_access_telescope = False
            self.can_access_inventory = True
            self.is_telescope_admin = False

        super().save(*args, **kwargs)

    @property
    def branch(self):
        """Exposes the linked inventory branch as a convenient alias property."""
        return self.inventory_branch

    @property
    def display_name(self):
        """
        Determines the best name to display.
        Uses nickname if present; otherwise full name; otherwise falls back to username.
        """
        if self.nickname:
            return self.nickname
        return self.get_full_name() or self.username

    @property
    def initials(self):
        """
        Generates 2-character uppercase initials from the user's name.
        Used for placeholder avatars. (e.g. 'John Doe' -> 'JD', 'operator' -> 'OP').
        """
        name = self.get_full_name()
        if name:
            parts = name.split()
            return "".join(p[0].upper() for p in parts[:2])
        return self.username[:2].upper()


class UserLoginHistory(models.Model):
    """
    Tracks account authentication history (login timestamp, IP address, User-Agent)
    for security auditing.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_histories")
    login_datetime = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-login_datetime']
        verbose_name_plural = "User Login Histories"

    def __str__(self):
        return f"{self.user.username} logged in at {self.login_datetime} ({self.ip_address})"


from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

def get_client_ip(request):
    if not request:
        return "127.0.0.1"
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or "127.0.0.1"

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if request and user and user.is_authenticated:
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:255]
        UserLoginHistory.objects.create(
            user=user,
            ip_address=ip,
            user_agent=ua
        )

