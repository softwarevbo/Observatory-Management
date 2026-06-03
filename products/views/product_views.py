import zipfile
import pandas as pd
import copy
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from audit.models import AuditLog
from inventory.models import Branch, BranchStock
from inventory.decorators import staff_permission_required
from inventory.utils import (
    has_global_inventory_access,
    get_isolated_products,
    filter_by_branch,
)
from tasks.decorators import admin_required
from ..models import Category, Product
from ..forms import ProductForm


@method_decorator(staff_permission_required("can_add_inventory"), name="dispatch")
class ProductCreateView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        initial_branch_id = request.GET.get("branch")
        initial_data = {"branch": initial_branch_id} if initial_branch_id else {}
        form = ProductForm(user=request.user, initial=initial_data)
        return render(request, "products/add_product.html", {"form": form})

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        form_type = request.POST.get("form_type")
        if form_type == "bulk":
            return self.handle_bulk_upload(request)
        form = ProductForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            if not has_global_inventory_access(request.user):
                product.branch = request.user.branch
            if form.cleaned_data.get("branch"):
                product.branch = form.cleaned_data.get("branch")
            product.save()
            BranchStock.objects.get_or_create(
                product=product,
                branch=product.branch or request.user.branch,
                defaults={
                    "rack_number": form.cleaned_data.get("rack_number", "-"),
                    "shelf_number": form.cleaned_data.get("shelf_number", "-"),
                    "local_sku": form.cleaned_data.get("local_sku"),
                },
            )
            AuditLog.log(request.user, "created", product)
            messages.success(request, f"Product '{product.name}' added successfully!")
            return redirect("products")
        return render(request, "products/add_product.html", {"form": form})

    def handle_bulk_upload(self, request):
        excel_file = request.FILES.get("excel_file")
        datasheet_zip = request.FILES.get("datasheet_zip")
        skip_duplicates = request.POST.get("skip_duplicates") == "on"
        if not excel_file:
            messages.error(request, "Please select an Excel file to upload.")
            return redirect("add-product")
        if excel_file.size > 5 * 1024 * 1024:
            messages.error(request, "File size must be less than 5MB.")
            return redirect("add-product")
        try:
            df = (
                pd.read_excel(excel_file, engine="openpyxl")
                if excel_file.name.endswith(".xlsx")
                else pd.read_excel(excel_file, engine="xlrd")
            )
            required_columns = ["Name", "SKU", "Price"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(
                    request, f"Missing required columns: {', '.join(missing_columns)}"
                )
                return redirect("add-product")
            success_count, error_count, skipped_count, errors = 0, 0, 0, []
            zip_files = {}
            if datasheet_zip:
                try:
                    with zipfile.ZipFile(datasheet_zip) as zf:
                        for name in zf.namelist():
                            zip_files[name] = zf.read(name)
                except Exception as e:
                    messages.error(request, f"Error reading datasheet ZIP: {e}")
                    return redirect("add-product")
            for index, row in df.iterrows():
                try:
                    name, sku, price = (
                        str(row["Name"]).strip(),
                        str(row["SKU"]).strip(),
                        float(row["Price"]),
                    )
                    if not name or not sku or pd.isna(price):
                        error_count += 1
                        errors.append(f"Row {index + 2}: Missing required fields")
                        continue
                    if Product.objects.filter(sku=sku).exists():
                        if skip_duplicates:
                            skipped_count += 1
                            continue
                        else:
                            error_count += 1
                            errors.append(
                                f'Row {index + 2}: SKU "{sku}" already exists'
                            )
                            continue
                    category = (
                        Category.objects.filter(
                            name__iexact=str(row["Category"]).strip()
                        ).first()
                        if "Category" in df.columns and not pd.isna(row["Category"])
                        else None
                    )
                    target_branch = (
                        Branch.objects.filter(
                            code__iexact=str(row["Branch (Code)"]).strip()
                        ).first()
                        if "Branch (Code)" in df.columns
                        and not pd.isna(row["Branch (Code)"])
                        else (
                            getattr(request.user, "branch", None)
                            if hasattr(request.user, "branch")
                            else None
                        )
                    )
                    datasheet_file = (
                        ContentFile(
                            zip_files[str(row["Datasheet Filename"]).strip()],
                            name=str(row["Datasheet Filename"]).strip(),
                        )
                        if "Datasheet Filename" in df.columns
                        and not pd.isna(row.get("Datasheet Filename"))
                        and str(row["Datasheet Filename"]).strip() in zip_files
                        else None
                    )
                    product = Product.objects.create(
                        name=name,
                        sku=sku,
                        price=price,
                        category=category,
                        branch=target_branch,
                        created_by=request.user,
                        datasheet=datasheet_file,
                        brand=(
                            str(row.get("Brand", "")).strip()
                            if "Brand" in df.columns and not pd.isna(row.get("Brand"))
                            else ""
                        ),
                        description=(
                            str(row.get("Description", "")).strip()
                            if "Description" in df.columns
                            and not pd.isna(row.get("Description"))
                            else ""
                        ),
                        serial_number=(
                            str(row.get("Serial Number", "")).strip()
                            if "Serial Number" in df.columns
                            and not pd.isna(row.get("Serial Number"))
                            else ""
                        ),
                    )
                    if target_branch:
                        BranchStock.objects.get_or_create(
                            product=product,
                            branch=target_branch,
                            defaults={
                                "rack_number": (
                                    str(row.get("Rack Number", "-")).strip()
                                    if "Rack Number" in df.columns
                                    else "-"
                                ),
                                "shelf_number": (
                                    str(row.get("Shelf Number", "-")).strip()
                                    if "Shelf Number" in df.columns
                                    else "-"
                                ),
                                "local_sku": (
                                    str(row.get("Local SKU", sku)).strip()
                                    if "Local SKU" in df.columns
                                    else sku
                                ),
                            },
                        )
                    AuditLog.log(request.user, "created", product)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
            if success_count > 0:
                messages.success(
                    request, f"Successfully imported {success_count} products!"
                )
            if skipped_count > 0:
                messages.warning(
                    request, f"Skipped {skipped_count} duplicate products."
                )
            if error_count > 0:
                error_message = f"Failed to import {error_count} products. " + (
                    "Errors: " + "; ".join(errors)
                    if len(errors) <= 5
                    else f"First 5 errors: {'; '.join(errors[:5])}"
                )
                messages.error(request, error_message)
            return redirect("products")
        except Exception as e:
            messages.error(request, f"Error processing Excel file: {str(e)}")
            return redirect("add-product")


class ProductListPageView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        is_global = has_global_inventory_access(request.user)
        user_branch = getattr(request.user, "branch", None)
        qs = BranchStock.objects.select_related(
            "product", "branch", "product__category", "product__created_by"
        )
        if not is_global and user_branch:
            qs = qs.filter(branch=user_branch)
        elif not is_global:
            qs = qs.none()
        search_query = request.GET.get("search", "")
        if search_query:
            qs = qs.filter(
                Q(product__name__icontains=search_query)
                | Q(product__sku__icontains=search_query)
                | Q(local_sku__icontains=search_query)
                | Q(product__brand__icontains=search_query)
                | Q(rack_number__icontains=search_query)
                | Q(shelf_number__icontains=search_query)
                | Q(product__serial_number__icontains=search_query)
            ).distinct()
        category_id = request.GET.get("category")
        if category_id:
            qs = qs.filter(product__category_id=category_id)
        branch_id = request.GET.get("branch")
        if branch_id and is_global:
            qs = qs.filter(branch_id=branch_id)
        status = request.GET.get("status")
        if status:
            qs = qs.filter(product__status=status)
        sort_by = request.GET.get("sort", "-product__created_at")
        qs = qs.order_by(sort_by)
        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(request.GET.get("page"))
        cloned_products = []
        for bs in page_obj:
            p = copy.copy(bs.product)
            (
                p.current_quantity,
                p.display_branch,
                p.branch_id,
                p.rack_number,
                p.shelf_number,
                p.local_sku,
                p.inventory_value,
            ) = (
                bs.current_quantity,
                bs.branch.name,
                bs.branch.id,
                bs.rack_number,
                bs.shelf_number,
                bs.local_sku,
                bs.current_quantity * (p.price or 0),
            )
            cloned_products.append(p)
        page_obj.object_list = cloned_products
        return render(
            request,
            "products/products_list.html",
            {
                "products": page_obj,
                "page_obj": page_obj,
                "categories": Category.objects.all(),
                "branches": Branch.objects.all() if is_global else [],
                "search_query": search_query,
                "current_category": category_id,
                "current_branch": branch_id,
                "current_status": status,
                "current_sort": sort_by,
            },
        )


class ProductDetailView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        from stock.models import StockEntry
        from inventory.models import Rental

        product = get_object_or_404(Product, pk=pk)
        is_global = has_global_inventory_access(request.user)
        user_branch = getattr(request.user, "branch", None)
        priority_branch_id = request.GET.get("branch")
        total_display_stock = (
            BranchStock.objects.filter(
                product=product, **({} if is_global else {"branch": user_branch})
            ).aggregate(Sum("current_quantity"))["current_quantity__sum"]
            or 0
        )
        branch_stocks = BranchStock.objects.filter(product=product).select_related(
            "branch"
        )
        if not is_global:
            branch_stocks = (
                branch_stocks.filter(branch=user_branch)
                if user_branch
                else branch_stocks.none()
            )
        highlighted_stock, highlighted_info = 0, {
            "rack": "-",
            "shelf": "-",
            "branch_name": "N/A",
        }
        target_branch = (
            Branch.objects.filter(id=priority_branch_id).first()
            if priority_branch_id and is_global
            else user_branch
        )
        if target_branch:
            lb = BranchStock.objects.filter(
                product=product, branch=target_branch
            ).first()
            if lb:
                highlighted_stock, highlighted_info = lb.current_quantity, {
                    "rack": lb.rack_number or "-",
                    "shelf": lb.shelf_number or "-",
                    "branch_name": target_branch.name,
                }
        rentals_qs = Rental.objects.filter(
            product=product, **({} if is_global else {"branch": user_branch})
        )
        return render(
            request,
            "products/product_detail.html",
            {
                "product": product,
                "branch_stocks": branch_stocks,
                "total_stock": total_display_stock,
                "highlighted_stock": highlighted_stock,
                "highlighted_info": highlighted_info,
                "priority_branch_id": (
                    int(priority_branch_id)
                    if priority_branch_id and priority_branch_id.isdigit() and is_global
                    else None
                ),
                "rental_count": rentals_qs.count(),
                "rental_quantity": rentals_qs.filter(status="active").aggregate(
                    Sum("quantity")
                )["quantity__sum"]
                or 0,
                "recent_stock_entries": filter_by_branch(
                    StockEntry.objects.filter(product=product), request.user
                ).order_by("-timestamp")[:10],
                "is_global": is_global,
                "branches": Branch.objects.all() if is_global else [],
            },
        )

    def post(self, request, pk):
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        if request.POST.get("action") == "stock_adjustment":
            adj_type, qty, reason = (
                request.POST.get("adjustment_type"),
                int(request.POST.get("quantity", 0)),
                request.POST.get("reason", "Manual adjustment from detail page"),
            )
            if qty > 0:
                target_branch = (
                    Branch.objects.filter(id=request.POST.get("branch")).first()
                    if request.POST.get("branch") and request.user.is_super_admin
                    else (getattr(request.user, "branch", None) or product.branch)
                )
                from stock.models import StockEntry

                bs, _ = BranchStock.objects.get_or_create(
                    product=product, branch=target_branch
                )
                StockEntry.objects.create(
                    product=product,
                    branch=target_branch,
                    quantity=qty,
                    entry_type=adj_type,
                    location_from=request.POST.get("location_from")
                    or f"Rack: {getattr(bs, 'rack_number', '-')}, Shelf: {getattr(bs, 'shelf_number', '-')}",
                    location_to=request.POST.get("location_to"),
                    description=reason,
                    created_by=request.user,
                )
                messages.success(request, f"Stock {adj_type} recorded successfully.")
            else:
                messages.error(request, "Invalid quantity.")
        return redirect("product-detail", pk=pk)


class ProductEditView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        return render(
            request,
            "products/edit_product.html",
            {
                "form": ProductForm(instance=product, user=request.user),
                "product": product,
            },
        )

    def post(self, request, pk):
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        form = ProductForm(
            request.POST, request.FILES, instance=product, user=request.user
        )
        if form.is_valid():
            if not has_global_inventory_access(request.user):
                form.instance.branch = product.branch
            updated_product = form.save()
            update_branch = (
                request.user.branch
                if not has_global_inventory_access(request.user)
                and getattr(request.user, "branch", None)
                else updated_product.branch
            )
            if update_branch:
                bs, _ = BranchStock.objects.get_or_create(
                    product=updated_product, branch=update_branch
                )
                bs.rack_number, bs.shelf_number, bs.local_sku = (
                    form.cleaned_data.get("rack_number") or "-",
                    form.cleaned_data.get("shelf_number") or "-",
                    form.cleaned_data.get("local_sku"),
                )
                bs.save()
            AuditLog.log(request.user, "updated", updated_product)
            messages.success(
                request, f"Product {updated_product.name} updated successfully!"
            )
            return redirect("products")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")
        return render(
            request, "products/edit_product.html", {"form": form, "product": product}
        )


class ProductDeleteView(View):
    @method_decorator(admin_required)
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        product_name = product.name
        product.delete()
        AuditLog.log(request.user, "deleted", None, f"Deleted product: {product_name}")
        messages.success(request, f"Product '{product_name}' has been deleted.")
        return redirect("products")
