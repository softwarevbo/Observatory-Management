from django import forms

from .models import Budget, Expense

"""
This module contains forms for managing project budgets and tracking expenses.
"""

class ExpenseForm(forms.ModelForm):
    """
    ModelForm used to track individual project expenses.
    Limits receipt attachments strictly to files linked to the target project.
    """
    class Meta:
        model = Expense
        fields = [
            "title",
            "amount",
            "category",
            "date_incurred",
            "description",
            "receipt",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. AWS Hosting"}
            ),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "date_incurred": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "receipt": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        """
        Overrides initialization to constrain receipt options.
        Only shows files belonging to the current project context.
        """
        super().__init__(*args, **kwargs)
        if project:
            self.fields["receipt"].queryset = project.files.all()
        else:
            self.fields["receipt"].queryset = project.files.none() if project else self.fields["receipt"].queryset.none()


class BudgetForm(forms.ModelForm):
    """
    ModelForm used to assign or update overall project budgets.
    """
    class Meta:
        model = Budget
        fields = ["total_amount"]
        widgets = {
            "total_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            )
        }
