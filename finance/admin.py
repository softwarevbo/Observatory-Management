from django.contrib import admin
from .models import Budget, Expense

"""
This module registers Finance application models with the Django Admin panel.
Provides list displays and filters for project budgets and expenses.
"""

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    """Admin configuration for project budgets."""
    list_display = ["project", "total_amount", "created_at", "updated_at"]
    search_fields = ["project__name"]
    raw_id_fields = ["project"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Admin configuration for project expenses."""
    list_display = ["title", "project", "amount", "category", "date_incurred", "logged_by"]
    list_filter = ["category", "date_incurred", "project"]
    search_fields = ["title", "description", "project__name", "logged_by__username"]
    raw_id_fields = ["project", "logged_by", "receipt"]
