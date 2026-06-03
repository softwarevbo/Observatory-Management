from django.contrib import admin
from .models import StockEntry, StockTransfer


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "branch",
        "quantity",
        "entry_type",
        "timestamp",
        "created_by",
    )
    list_filter = ("entry_type", "branch", "timestamp")
    search_fields = ("product__name", "description")


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "from_branch",
        "to_branch",
        "quantity",
        "status",
        "created_at",
        "received_at",
    )
    list_filter = ("status", "from_branch", "to_branch", "created_at")
    search_fields = ("product__name", "notes")
