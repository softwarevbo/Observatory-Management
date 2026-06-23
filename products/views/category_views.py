from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from audit.models import AuditLog
from tasks.decorators import admin_required
from inventory.decorators import staff_permission_required, branch_admin_required, super_admin_required
from ..models import Category

"""
This module processes view controllers for adding, editing, listing, and deleting Product Categories.
"""


class CategoryListPageView(View):
    """
    Renders list view of product categories.
    """
    def get(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Fetch all product category records from the database
        categories = Category.objects.all()
        # Paginate results with 25 categories per page
        paginator = Paginator(categories, 25)
        # Fetch the active page requested
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        # Render categories list template and pass page context
        return render(
            request,
            "products/categories_list.html",
            {"categories": page_obj, "page_obj": page_obj},
        )


@method_decorator(staff_permission_required("can_add_inventory"), name="dispatch")
class CategoryCreateView(View):
    """
    Handles rendering the category entry form (GET) and creating a Category (POST).
    """
    def get(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Render form to enter a new Category
        return render(request, "products/add_category.html")

    def post(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Extract form field inputs from POST body parameters
        name = request.POST.get("name")
        description = request.POST.get("description")
        # Extract uploaded file for category icon representation
        image = request.FILES.get("image")
        
        # Save Category record in database
        category = Category.objects.create(
            name=name, description=description, image=image
        )
        
        # Add creation audit trace log to track action history
        AuditLog.log(request.user, "created", category)
        # Display feedback message to the user
        messages.success(request, "Category added successfully!")
        # Redirect to categories list view
        return redirect("categories")


@method_decorator(branch_admin_required, name="dispatch")
class CategoryEditView(View):
    """
    Renders edit category form (GET) and processes category updates (POST).
    """
    def get(self, request, pk):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Query category instance or return 404
        category = get_object_or_404(Category, pk=pk)
        # Render the edit category page template passing the category instance
        return render(request, "products/edit_category.html", {"category": category})

    def post(self, request, pk):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Retrieve target category instance to perform update
        category = get_object_or_404(Category, pk=pk)
        # Update attributes from form fields
        category.name = request.POST.get("name")
        category.description = request.POST.get("description")
        # Update image field only if a new image file is uploaded
        if request.FILES.get("image"):
            category.image = request.FILES.get("image")
        # Save modifications to database
        category.save()
        
        # Add update audit trace log to record changes
        AuditLog.log(request.user, "updated", category)
        # Display confirmation alert to user
        messages.success(request, "Category updated successfully!")
        # Redirect to categories list view
        return redirect("categories")


@method_decorator(super_admin_required, name="dispatch")
class CategoryDeleteView(View):
    """
    Handles permanent deletion of categories.
    """
    def post(self, request, pk):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Retrieve target category record or return 404
        category = get_object_or_404(Category, pk=pk)
        name = category.name
        # Delete category (sets product.category to NULL on products belonging to it)
        category.delete()
        
        # Add deletion audit log trace to record action
        AuditLog.log(request.user, "deleted", None, f"Deleted category: {name}")
        # Display confirmation alert
        messages.success(request, f"Category '{name}' deleted successfully!")
        # Redirect to categories list view
        return redirect("categories")
