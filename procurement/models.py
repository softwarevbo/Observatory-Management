from django.db import models

"""
This module defines the database models for the Procurement application.
It establishes schemas for procurement requests, quantities required, and decision tracking.
"""


class ProcurementRequest(models.Model):
    """
    Model representing procurement requests submitted by branch users.
    Tracks target product, requested and fulfilled quantities, branch scopes, and admin decision parameters.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    requester = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_requests",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_requests",
    )
    branch = models.ForeignKey(
        "inventory.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_requests",
    )
    product_name = models.CharField(max_length=255)
    requested_quantity = models.PositiveIntegerField()
    current_stock = models.IntegerField(default=0)
    rack_number = models.CharField(max_length=100, blank=True, null=True)
    shelf_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    note = models.TextField(blank=True, null=True)
    decision_reason = models.TextField(blank=True, null=True)
    fulfilled_quantity = models.PositiveIntegerField(default=0)
    decided_by = models.ForeignKey(
        "inventory.InventoryUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_procurement_requests",
    )
    decided_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product_name} x {self.requested_quantity} ({self.status})"
