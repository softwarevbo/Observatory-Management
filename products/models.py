from django.db import models

"""
This module defines the database schema for Products and Categories.
It forms the core data structure of the inventory management system, enabling items to be
classified into categories, linked to branches, tracked by SKU/serial numbers, and audited.
"""


class Category(models.Model):
    """
    Represents a product category to organize different items in the inventory.
    """
    # Unique category name (e.g., "Electronic Components")
    name = models.CharField(max_length=100, unique=True)
    # Optional description of what type of products belong to this category
    description = models.TextField(blank=True, null=True)
    # Optional category image/icon representation
    image = models.ImageField(upload_to="category_images/", blank=True, null=True)

    def __str__(self):
        # Human-readable string representation of a category
        return self.name

    @staticmethod
    def create_default_categories():
        """
        Populates default product categories in the database.
        Useful during initial setup or database seeding.
        """
        default_categories = [
            "Consumer Electronics",
            "Home Entertainment",
            "Audio Equipment",
            "Cameras & Photography",
            "Smart Home Devices",
            "Gaming Devices",
            "Computer Accessories & Peripherals",
            "Electronic Components",
            "Power & Charging Devices",
        ]
        # Iterate over names and use get_or_create to prevent creating duplicates
        for cat in default_categories:
            Category.objects.get_or_create(name=cat)


class Product(models.Model):
    """
    Represents a specific product model details in the master catalog.
    Keeps general product dimensions (price, brand, description, global SKU, serial number)
    independent of branch-specific quantities (which are stored in BranchStock).
    """
    STATUS_CHOICES = [
        ("in_stock", "In Stock"),
        ("low_stock", "Low Stock"),
        ("out_of_stock", "Out of Stock"),
        ("damaged", "Damaged"),
        ("lost", "Lost"),
    ]

    # Name of the product
    name = models.CharField(max_length=200)
    # Link to category model; set to NULL on deletion of category to avoid cascade deletes
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="products"
    )
    # Optional branch assignment. If null, the product is global (available to all branches)
    branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.CASCADE,
        related_name="branch_products",
        null=True,
        blank=True,
    )
    # Product brand/manufacturer name
    brand = models.CharField(max_length=100, blank=True, null=True)
    # Detailed description of the product specification
    description = models.TextField(blank=True, null=True)
    # Stock Keeping Unit (global barcode/identifier)
    sku = models.CharField(max_length=100, blank=True, null=True)
    # Unique serial number (indexed for faster query lookup)
    serial_number = models.CharField(
        max_length=100, db_index=True, blank=True, null=True
    )
    # Model number of the product
    model_number = models.CharField(max_length=100, blank=True, null=True)
    # Standard unit of measurement (default is "Units")
    unit = models.CharField(
        max_length=50, default="Units", help_text="e.g., Pcs, Kg, Mtr"
    )
    # Condition/Availability status of the product
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_stock")
    # Supplier/vendor details
    supplier = models.CharField(max_length=200, blank=True, null=True)
    # Text notes regarding procurement details
    purchase_details = models.TextField(blank=True, null=True)

    # Track who created this product record
    created_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional image and datasheet attachments
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
    datasheet = models.FileField(upload_to="product_datasheets/", blank=True, null=True)

    def __str__(self):
        # Display name with SKU for unique identification
        return f"{self.name} ({self.sku})"

    class Meta:
        # Sort products by default in reverse chronological order (newest first)
        ordering = ["-created_at"]
