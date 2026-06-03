from django.contrib.auth import get_user_model
from django.db import models
from products.models import Product

User = get_user_model()


class StockEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("in", "Stock In"),
        ("out", "Stock Out"),
        ("transfer", "Transfer"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_entries"
    )
    branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.CASCADE,
        related_name="stock_entries",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    location_from = models.CharField(max_length=100, blank=True, null=True)
    location_to = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f"{self.get_entry_type_display()} - {self.product.name} ({self.quantity})"
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ("pending", "In Transit"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="transfers"
    )
    from_branch = models.ForeignKey(
        "inventory.Branch", on_delete=models.CASCADE, related_name="transfers_out"
    )
    to_branch = models.ForeignKey(
        "inventory.Branch", on_delete=models.CASCADE, related_name="transfers_in"
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Storage details at destination
    rack_number = models.CharField(max_length=50, blank=True, null=True)
    shelf_number = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_created",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_received",
    )
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Transfer: {self.product.name} ({self.quantity}) from {self.from_branch.code} to {self.to_branch.code}"
