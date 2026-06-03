from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from audit.models import AuditLog
from tasks.decorators import admin_required
from ..models import Category


class CategoryListPageView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        categories = Category.objects.all()
        paginator = Paginator(categories, 25)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        return render(
            request,
            "products/categories_list.html",
            {"categories": page_obj, "page_obj": page_obj},
        )


class CategoryCreateView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        return render(request, "products/add_category.html")

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")
        category = Category.objects.create(
            name=name, description=description, image=image
        )
        AuditLog.log(request.user, "created", category)
        messages.success(request, "Category added successfully!")
        return redirect("categories")


class CategoryEditView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        category = get_object_or_404(Category, pk=pk)
        return render(request, "products/edit_category.html", {"category": category})

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        category = get_object_or_404(Category, pk=pk)
        category.name = request.POST.get("name")
        category.description = request.POST.get("description")
        if request.FILES.get("image"):
            category.image = request.FILES.get("image")
        category.save()
        AuditLog.log(request.user, "updated", category)
        messages.success(request, "Category updated successfully!")
        return redirect("categories")


class CategoryDeleteView(View):
    @method_decorator(admin_required)
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        category = get_object_or_404(Category, pk=pk)
        name = category.name
        category.delete()
        AuditLog.log(request.user, "deleted", None, f"Deleted category: {name}")
        messages.success(request, f"Category '{name}' deleted successfully!")
        return redirect("categories")
