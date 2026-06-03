from django.db import models
from django import forms
from .models import Product, Category
from inventory.models import Branch, BranchStock


class ProductForm(forms.ModelForm):
    rack_number = forms.CharField(max_length=50, required=False, initial="-")
    shelf_number = forms.CharField(max_length=50, required=False, initial="-")
    local_sku = forms.CharField(
        max_length=100, required=False, label="Branch Specific SKU"
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "branch",
            "brand",
            "description",
            "sku",
            "serial_number",
            "price",
            "unit",
            "status",
            "supplier",
            "purchase_details",
            "image",
            "datasheet",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "purchase_details": forms.Textarea(attrs={"rows": 3}),
            "name": forms.TextInput(attrs={"placeholder": "Enter product name"}),
            "sku": forms.TextInput(
                attrs={"placeholder": "Global SKU (Read-only for staff)"}
            ),
            "price": forms.NumberInput(attrs={"step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Add Bootstrap classes to all fields
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        # Specific styling for select fields
        self.fields["category"].widget.attrs.update({"class": "form-select"})
        self.fields["branch"].widget.attrs.update({"class": "form-select"})
        self.fields["status"].widget.attrs.update({"class": "form-select"})

        # Logic for Branch field visibility and assignment
        is_global = False
        if user:
            from inventory.utils import has_global_inventory_access

            is_global = has_global_inventory_access(user)

            if not is_global:
                # Non-super admins cannot change branch
                self.fields["branch"].widget = forms.HiddenInput()
                self.fields["branch"].required = False
                if not self.instance.pk and hasattr(user, "branch"):
                    self.fields["branch"].initial = user.branch

                # Make global SKU read-only for branch staff to prevent "linking"
                self.fields["sku"].widget.attrs["readonly"] = True
            else:
                # Super Admin can see all branches
                self.fields["branch"].queryset = Branch.objects.all()
                self.fields["branch"].required = False  # Allow global products
                self.fields["branch"].empty_label = "Global / No Branch"

        # Load initial values for rack/shelf/local_sku if editing
        if self.instance and self.instance.pk:
            # We need a branch to find the branch-specific info
            current_branch = None
            if user:
                if not is_global and hasattr(user, "branch") and user.branch:
                    current_branch = user.branch

            if not current_branch:
                current_branch = self.instance.branch

            if current_branch:
                bs = BranchStock.objects.filter(
                    product=self.instance, branch=current_branch
                ).first()
                if bs:
                    self.initial["rack_number"] = bs.rack_number
                    self.initial["shelf_number"] = bs.shelf_number
                    self.initial["local_sku"] = bs.local_sku
