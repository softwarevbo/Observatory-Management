from django.db import models
from django import forms
from .models import Product, Category
from inventory.models import Branch, BranchStock

"""
This module contains the forms for adding and editing products.
It handles branch visibility isolation and automatically synchronizes branch-specific
storage locations (rack, shelf) and local SKUs to the BranchStock model on saving.
"""


class ProductForm(forms.ModelForm):
    """
    Model form for creating and editing Product records.
    Declares virtual fields for rack_number, shelf_number, and local_sku,
    which exist on the BranchStock model rather than the Product model.
    """
    # Virtual fields to manage BranchStock location parameters on the same form screen
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
        # Extract user keyword parameter to perform branch access scoping
        user = kwargs.pop("user", None)
        # Call base constructor
        super().__init__(*args, **kwargs)

        # Iterate over all fields to dynamically add Bootstrap class "form-control"
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        # Apply specific styling class "form-select" for dropdown selection menus
        self.fields["category"].widget.attrs.update({"class": "form-select"})
        self.fields["branch"].widget.attrs.update({"class": "form-select"})
        self.fields["status"].widget.attrs.update({"class": "form-select"})

        # Check global access rights of the current active user
        is_global = False
        if user:
            from inventory.utils import has_global_inventory_access

            # Resolve if current user has global administration permissions
            is_global = has_global_inventory_access(user)

            if not is_global:
                # 1. Non-global/staff users cannot assign products to other branches.
                # Hide the branch input field from UI and set required to False.
                self.fields["branch"].widget = forms.HiddenInput()
                self.fields["branch"].required = False
                
                # If creating a new product record, default the initial branch to the user's home branch
                if not self.instance.pk and hasattr(user, "branch"):
                    self.fields["branch"].initial = user.branch

                # 2. Make global SKU read-only for branch staff to prevent unintended catalog modifications.
                self.fields["sku"].widget.attrs["readonly"] = True
            else:
                # 3. Super Admins or global managers can assign products to any branch.
                # Populate all branch options and allow empty branch for global catalog items.
                self.fields["branch"].queryset = Branch.objects.all()
                self.fields["branch"].required = False
                # Use empty label for global catalog items
                self.fields["branch"].empty_label = "Global / No Branch"

        # If editing an existing product instance, populate initial values for the virtual fields
        if self.instance and self.instance.pk:
            current_branch = None
            if user:
                # Determine which branch stock details to query.
                # Non-global users can only query stock levels matching their home branch.
                if not is_global and hasattr(user, "branch") and user.branch:
                    current_branch = user.branch

            # If user has global access, default to querying the product's primary branch assignment
            if not current_branch:
                current_branch = self.instance.branch

            # If a valid branch is resolved, fetch its rack/shelf/local SKU specifications from BranchStock table
            if current_branch:
                bs = BranchStock.objects.filter(
                    product=self.instance, branch=current_branch
                ).first()
                if bs:
                    # Populate the virtual form fields from BranchStock attributes
                    self.initial["rack_number"] = bs.rack_number
                    self.initial["shelf_number"] = bs.shelf_number
                    self.initial["local_sku"] = bs.local_sku
