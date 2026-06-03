from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("project/<int:project_id>/", views.project_expenses, name="project_expenses"),
    path(
        "project/<int:project_id>/expense/add/",
        views.expense_create,
        name="expense_create",
    ),
    path("project/<int:project_id>/budget/", views.budget_edit, name="budget_edit"),
]
