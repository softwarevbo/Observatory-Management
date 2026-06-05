from django.contrib import admin
from .models import ProcurementRequest

"""
This module registers the Procurement application models in the Django Admin portal.
"""

@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    """
    Admin configuration for ProcurementRequest model.
    Organizes search indices, list filters, and display fields.
    """
    list_display = (
        "id",
        "product_name",
        "requested_quantity",
        "fulfilled_quantity",
        "current_stock",
        "status",
        "requester",
        "decided_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("product_name", "requester__username", "note", "decision_reason")
