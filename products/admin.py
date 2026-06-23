from django.contrib import admin

from .models import Category, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "sku",
        "model_number",
        "category",
        "branch",
        "status",
        "created_at",
    )
    search_fields = ("name", "brand", "sku", "serial_number")
    list_filter = ("category", "branch", "status")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "image")
    search_fields = ("name",)
