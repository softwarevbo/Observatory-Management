from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import Project
from files.models import ProjectFile
from .models import Budget, Expense
from .forms import ExpenseForm
from decimal import Decimal

"""
This module contains unit tests validating the Finance models and forms.
"""

User = get_user_model()

class FinanceTestCase(TestCase):
    """Test suite validating budget calculations and expense constraints."""

    def setUp(self):
        # Create user accounts
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password", role="admin"
        )
        self.member = User.objects.create_user(
            username="member", email="member@example.com", password="password", role="member"
        )

        # Initialize projects
        self.project = Project.objects.create(
            name="Alpha Project",
            description="Alpha descriptions",
            created_by=self.admin
        )
        self.project.members.add(self.member)

        self.project2 = Project.objects.create(
            name="Beta Project",
            description="Beta descriptions",
            created_by=self.admin
        )

        # Initialize Budgets
        self.budget = Budget.objects.create(
            project=self.project,
            total_amount=Decimal("10000.00")
        )

        # Initialize File Attachments
        self.receipt = ProjectFile.objects.create(
            original_name="receipt.png",
            project=self.project,
            uploaded_by=self.admin
        )

        self.receipt2 = ProjectFile.objects.create(
            original_name="receipt2.png",
            project=self.project2,
            uploaded_by=self.admin
        )

    def test_budget_expenses_aggregation(self):
        """Verifies that budget total_expenses and remaining_budget calculations aggregate correctly."""
        # Log hardware expense
        Expense.objects.create(
            project=self.project,
            title="Laptops Purchase",
            amount=Decimal("1500.50"),
            category="hardware",
            date_incurred="2026-06-01",
            logged_by=self.admin,
            receipt=self.receipt
        )

        # Log software license expense
        Expense.objects.create(
            project=self.project,
            title="IDE Licenses",
            amount=Decimal("500.00"),
            category="software",
            date_incurred="2026-06-02",
            logged_by=self.member
        )

        # Check aggregate properties
        self.assertEqual(self.budget.total_expenses, Decimal("2000.50"))
        self.assertEqual(self.budget.remaining_budget, Decimal("7999.50"))

    def test_expense_form_receipt_queryset(self):
        """Ensures that the ExpenseForm limits selectable receipt options to files inside the target project."""
        # Initialize form with project context
        form = ExpenseForm(project=self.project)
        receipt_queryset = form.fields["receipt"].queryset

        # Should include self.receipt but exclude self.receipt2
        self.assertTrue(receipt_queryset.filter(pk=self.receipt.pk).exists())
        self.assertFalse(receipt_queryset.filter(pk=self.receipt2.pk).exists())
