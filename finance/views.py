from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from tasks.decorators import manager_or_admin_required
from tasks.models import Project

from .forms import BudgetForm, ExpenseForm
from .models import Budget

"""
This module processes project budgets and expense-tracking controllers.
"""

@login_required
def project_expenses(request, project_id):
    """
    Renders project expense summary dashboard and logs list.
    Verifies that the user is an admin or belongs to the project (member or manager).
    """
    project = get_object_or_404(Project, pk=project_id)

    # Validate access rights
    if not request.user.is_admin:
        if not (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
        ):
            messages.error(request, "You do not have access to this project.")
            return redirect("tasks:project_list")

    # Fetch expenses and pre-select related logging authors and receipts to prevent N+1 queries
    expenses = project.expenses.all().select_related("logged_by", "receipt")

    try:
        budget = project.budget
    except Budget.DoesNotExist:
        budget = None

    return render(
        request,
        "finance/project_expenses.html",
        {
            "project": project,
            "expenses": expenses,
            "budget": budget,
        },
    )


@login_required
@manager_or_admin_required
def expense_create(request, project_id):
    """
    Renders expense submission forms and records new project costs.
    Restricted to managers or administrators.
    """
    project = get_object_or_404(Project, pk=project_id)

    if request.method == "POST":
        form = ExpenseForm(request.POST, project=project)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.project = project
            expense.logged_by = request.user
            expense.save()
            messages.success(request, "Expense tracked successfully.")
            return redirect("finance:project_expenses", project_id=project.pk)
    else:
        form = ExpenseForm(project=project)

    return render(
        request,
        "finance/expense_form.html",
        {"form": form, "project": project, "title": "Track Expense"},
    )


@login_required
@manager_or_admin_required
def budget_edit(request, project_id):
    """
    Renders budget modification panels.
    Creates or updates the OneToOne Budget link relative to the project.
    Restricted to managers or administrators.
    """
    project = get_object_or_404(Project, pk=project_id)

    try:
        budget = project.budget
    except Budget.DoesNotExist:
        budget = Budget(project=project)

    if request.method == "POST":
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget updated.")
            return redirect("finance:project_expenses", project_id=project.pk)
    else:
        form = BudgetForm(instance=budget)

    return render(
        request,
        "finance/budget_form.html",
        {"form": form, "project": project, "title": "Edit Project Budget"},
    )
