from django import forms

from .models import Budget, Expense


class ExpenseForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)
        if project:
            # Only allow selecting files uploaded to this project
            self.fields["receipt"].queryset = project.files.all()


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["total_amount"]
        widgets = {
            "total_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            )
        }
