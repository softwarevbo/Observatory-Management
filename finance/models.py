from django.conf import settings
from django.db import models


class Budget(models.Model):
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
        return sum(expense.amount for expense in self.project.expenses.all())

    @property
    def remaining_budget(self):
        return self.total_amount - self.total_expenses


class Expense(models.Model):
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
