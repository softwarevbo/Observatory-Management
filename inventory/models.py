from django.contrib.auth import get_user_model
from django.db import models
from django.contrib.auth.hashers import check_password, make_password

from products.models import Product

"""
This module defines database models for the Inventory Management system.
Supports multi-branch storage isolation, stock adjustments, serial numbers, alert configurations, 
rentals tracking, and a separate user permissions schema.
"""

User = get_user_model()


class Branch(models.Model):
    """
    Model representing a physical IIA branch office or repository.
    Includes uniquely identifying codes (e.g. KOR, HOS).
    """
    code = models.CharField(max_length=20, unique=True, help_text="e.g., KOR, HOS, HAN")
    name = models.CharField(max_length=200, help_text="e.g., IIA, Koramangala")
    address = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class BranchStock(models.Model):
    """
    Model representing stock levels for a specific product at a specific branch.
    Tracks location attributes (rack/shelf) and local SKU codes.
    """
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stocks")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="branch_stocks"
    )
    current_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    rack_number = models.CharField(max_length=50, blank=True, null=True)
    shelf_number = models.CharField(max_length=50, blank=True, null=True)
    local_sku = models.CharField(max_length=100, blank=True, null=True)
    low_stock_limit = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "product")
        verbose_name = "Branch Stock"
        verbose_name_plural = "Branch Stocks"

    def __str__(self):
        return f"{self.product.name} at {self.branch.code} ({self.current_quantity})"


class InventoryAdjustment(models.Model):
    """
    Model tracking manual or automated stock level adjustments (increments/decrements).
    Linked directly to the Branch Stock calculation pipeline.
    """
    ADJUSTMENT_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("automated", "Automated"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="adjustments"
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="adjustments",
        null=True,
        blank=True,
    )
    adjustment_type = models.CharField(max_length=10, choices=ADJUSTMENT_TYPE_CHOICES)
    quantity = models.IntegerField()
    reason = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.adjustment_type} adjustment for {self.product.name} ({self.quantity})"


class SerialNumber(models.Model):
    """
    Model tracking individual serial numbers for inventory items.
    Allows auditing status transitions of highly sensitive equipment.
    """
    STATUS_CHOICES = [
        ("available", "Available"),
        ("sold", "Sold"),
        ("returned", "Returned"),
        ("damaged", "Damaged"),
    ]

    serial_number = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="serial_numbers"
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="serial_numbers",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="available"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.serial_number} - {self.product.name} ({self.status})"

    class Meta:
        ordering = ["-created_at"]


class QuantityLimit(models.Model):
    """
    Model defining branch-specific threshold bounds for low stock alerts.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="quantity_limits"
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="quantity_limits",
        null=True,
        blank=True,
    )
    limit_quantity = models.PositiveIntegerField(
        help_text="Alert will be triggered when quantity reaches this limit"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.product.name} - Limit: {self.limit_quantity}"

    class Meta:
        verbose_name = "Quantity Limit"
        verbose_name_plural = "Quantity Limits"


class Alert(models.Model):
    """
    Model capturing low stock or boundary alerts generated in the system.
    Audits active, acknowledged, or resolved states and handlers.
    """
    ALERT_TYPE_CHOICES = [
        ("low_stock", "Low Stock"),
        ("out_of_stock", "Out of Stock"),
        ("limit_reached", "Limit Reached"),
    ]

    ALERT_STATUS_CHOICES = [
        ("active", "Active"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="alerts"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="alerts", null=True, blank=True
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    status = models.CharField(
        max_length=15, choices=ALERT_STATUS_CHOICES, default="active"
    )
    message = models.TextField()
    current_quantity = models.PositiveIntegerField()
    limit_quantity = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )
    resolved_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts",
    )

    def __str__(self):
        return f"{self.product.name} - {self.get_alert_type_display()} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"


class Rental(models.Model):
    """
    Model logging equipment rentals or leases to external persons or institutions.
    """
    STATUS_CHOICES = [
        ("active", "Active"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
    ]
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="rentals"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="rentals", null=True, blank=True
    )
    quantity = models.PositiveIntegerField()
    rented_to = models.CharField(max_length=255)
    reason = models.TextField(blank=True, null=True)
    rental_date = models.DateField()
    rental_time = models.TimeField()
    return_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_by = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} rented to {self.rented_to} ({self.quantity})"


class StandardLimit(models.Model):
    """
    Model defining global low stock check quantity limits if no specific limits are set.
    """
    value = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Standard Limit: {self.value}"


class InventoryUser(models.Model):
    """
    Standalone isolated user catalog exclusively for Inventory Management pages.
    Includes custom permission boolean attributes governing sub-page views access levels.
    """
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(
        max_length=50,
        default="staff",
        choices=[
            ("super_admin", "Super Admin"),
            ("branch_admin", "Branch Admin"),
            ("staff", "Staff"),
        ],
    )
    branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Granular permission flags
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
    can_view_all_branches_inventory = models.BooleanField(default=False)
    can_add_inventory = models.BooleanField(default=True)
    can_edit_inventory = models.BooleanField(default=True)
    can_delete_inventory = models.BooleanField(default=False)
    can_approve_transfer = models.BooleanField(default=False)
    can_export_reports = models.BooleanField(default=True)
    can_manage_users = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        """Hashes and sets user password."""
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        """Verifies if raw password matches the stored hash."""
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Inventory User"
        verbose_name_plural = "Inventory Users"

    @property
    def display_name(self):
        return self.username

    @property
    def is_super_admin(self):
        return self.role == "super_admin"

    @property
    def is_branch_admin(self):
        return self.role == "branch_admin"

    @property
    def is_admin(self):
        return self.role in ["super_admin", "branch_admin"]

    @property
    def is_staff(self):
        return self.role == "staff"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class InventoryNotification(models.Model):
    """
    Model representing notifications directed to Inventory Users.
    """
    NOTIFICATION_TYPE_CHOICES = [
        ("stock_in", "Stock In"),
        ("stock_out", "Stock Out"),
        ("procurement_request", "Procurement Request"),
        ("inventory_action", "Inventory Action"),
    ]

    recipient = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.CASCADE,
        related_name="inventory_notifications",
    )
    sender = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_inventory_notifications",
    )
    notification_type = models.CharField(
        max_length=30, choices=NOTIFICATION_TYPE_CHOICES, default="inventory_action"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_url = models.CharField(max_length=300, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"


class SystemSettings(models.Model):
    """
    Model representing system-wide settings or branch-specific feature configuration flags.
    """
    site_name = models.CharField(max_length=100, default="IIA Inventory Management")
    site_logo = models.ImageField(upload_to="settings/logos/", null=True, blank=True)
    contact_email = models.EmailField(default="support@iiap.res.in")

    branch = models.OneToOneField(
        Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="settings"
    )

    enable_notifications = models.BooleanField(default=True)
    enable_low_stock_alerts = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        if self.branch:
            return f"Settings for {self.branch.name}"
        return "Global System Settings"

    @staticmethod
    def get_settings(branch=None):
        """
        Retrieves global settings or configures one if missing.
        """
        if branch:
            settings, _ = SystemSettings.objects.get_or_create(branch=branch)
            return settings
        settings, _ = SystemSettings.objects.get_or_create(branch=None)
        return settings


class InventoryMessage(models.Model):
    """
    Model representing a direct message sent between Inventory Users.
    Uses simple DB polling (no WebSockets) because InventoryUsers are not
    standard Django auth users and cannot authenticate via Channels.
    """
    sender = models.ForeignKey(
        InventoryUser,
        on_delete=models.CASCADE,
        related_name="sent_inv_messages",
    )
    recipient = models.ForeignKey(
        InventoryUser,
        on_delete=models.CASCADE,
        related_name="received_inv_messages",
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Inventory Message"
        verbose_name_plural = "Inventory Messages"

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}: {self.content[:40]}"
