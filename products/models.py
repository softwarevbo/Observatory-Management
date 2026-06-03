from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="category_images/", blank=True, null=True)

    def __str__(self):
        return self.name

    @staticmethod
    def create_default_categories():
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
        for cat in default_categories:
            Category.objects.get_or_create(name=cat)


class Product(models.Model):
    STATUS_CHOICES = [
        ("in_stock", "In Stock"),
        ("low_stock", "Low Stock"),
        ("out_of_stock", "Out of Stock"),
        ("damaged", "Damaged"),
        ("lost", "Lost"),
    ]

    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="products"
    )
    branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.CASCADE,
        related_name="branch_products",
        null=True,
        blank=True,
    )
    brand = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    sku = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(
        max_length=100, unique=True, db_index=True, blank=True, null=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    unit = models.CharField(
        max_length=50, default="Units", help_text="e.g., Pcs, Kg, Mtr"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_stock")
    supplier = models.CharField(max_length=200, blank=True, null=True)
    purchase_details = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
    datasheet = models.FileField(upload_to="product_datasheets/", blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    class Meta:
        ordering = ["-created_at"]
