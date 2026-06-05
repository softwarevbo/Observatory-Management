from django.conf import settings
from django.db import models

"""
This module contains the database models for the Finance system.
It establishes schemas for project budgets and individual expenses.
"""

class Budget(models.Model):
    """
    Model representing total financial bounds allocated to a project.
    Uses a OneToOneField linking to the Project model, restricting each project to a single budget.
    """
    project = models.OneToOneField(
        "tasks.Project", on_delete=models.CASCADE, related_name="budget"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Budget for {self.project.name}"

    @property
    def total_expenses(self):
        """
        Dynamically aggregates the sum of all expenses logged against the project.
        Uses Python's sum generator; for large datasets, a DB aggregation (Sum) is recommended.
        """
        return sum(expense.amount for expense in self.project.expenses.all())

    @property
    def remaining_budget(self):
        """Calculates the remaining balance in real time."""
        return self.total_amount - self.total_expenses


class Expense(models.Model):
    """
    Model representing individual expenses logged against projects.
    Supports categorizations, logging authors, and links to Project Files for receipt storage.
    """
    CATEGORY_CHOICES = [
        ("hardware", "Hardware / Equipment"),
        ("software", "Software / Licenses"),
        ("travel", "Travel & Accommodation"),
        ("services", "External Services"),
        ("materials", "Materials / Components"),
        ("other", "Other"),
    ]

    project = models.ForeignKey(
        "tasks.Project", on_delete=models.CASCADE, related_name="expenses"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )
    date_incurred = models.DateField()
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="logged_expenses",
    )
    receipt = models.ForeignKey(
        "files.ProjectFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        help_text="Attached receipt from Project Files",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_incurred", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.amount})"
