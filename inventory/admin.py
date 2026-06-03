from django.contrib import admin
from .models import (
    Alert,
    Branch,
    BranchStock,
    InventoryAdjustment,
    QuantityLimit,
    SerialNumber,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_number", "is_active", "created_at")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(BranchStock)
class BranchStockAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "branch",
        "current_quantity",
        "local_sku",
        "rack_number",
        "shelf_number",
        "last_updated",
    )
    list_filter = ("branch", "last_updated")
    search_fields = ("product__name", "local_sku", "rack_number", "shelf_number")
    list_editable = ("rack_number", "shelf_number")


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "adjustment_type",
        "quantity",
        "reason",
        "timestamp",
        "created_by",
    )
    list_filter = ("adjustment_type", "timestamp")
    search_fields = ("product__name", "reason")


@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "product", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("serial_number", "product__name")


@admin.register(QuantityLimit)
class QuantityLimitAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "limit_quantity",
        "is_active",
        "created_at",
        "created_by",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("product__name", "product__sku")
    list_editable = ("is_active",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "alert_type",
        "status",
        "current_quantity",
        "limit_quantity",
        "created_at",
    )
    list_filter = ("alert_type", "status", "created_at")
    search_fields = ("product__name", "message")
    readonly_fields = ("created_at", "acknowledged_at", "resolved_at")
    list_editable = ("status",)


from django import forms

from .models import InventoryNotification, InventoryUser


class InventoryUserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Leave blank to keep current password"}
        ),
        required=False,
        help_text="Set or change the user's password here.",
    )

    class Meta:
        model = InventoryUser
        fields = "__all__"


@admin.register(InventoryUser)
class InventoryUserAdmin(admin.ModelAdmin):
    form = InventoryUserForm
    list_display = ("username", "role", "email", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get("password")
        if password:
            obj.set_password(password)
        super().save_model(request, obj, form, change)


@admin.register(InventoryNotification)
class InventoryNotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "title", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "sender__username", "title", "message")
