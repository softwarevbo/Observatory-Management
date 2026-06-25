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
from inventory.decorators import staff_permission_required, branch_admin_required, super_admin_required
from inventory.utils import (
    has_global_inventory_access,
    get_isolated_products,
    filter_by_branch,
)
from django.forms import modelformset_factory
from tasks.decorators import admin_required
from ..models import Category, Product
from ..forms import ProductForm, BulkProductForm

"""
This module processes view controllers for product catalog creation, updates, deletion,
searches, and bulk spreadsheet imports.
"""


@method_decorator(staff_permission_required("can_add_inventory"), name="dispatch")
class ProductCreateView(View):
    """
    Handles rendering the product entry form (GET) and processing single/bulk product uploads (POST).
    """
    ProductFormSet = modelformset_factory(
        Product,
        form=BulkProductForm,
        extra=1,
        can_delete=True,
    )

    def get(self, request):
        # Ensure user is logged in
        if not request.user.is_authenticated:
            # Redirect to log-in screen if session is not authenticated
            return redirect("accounts:login")
        # Extract pre-selected branch if coming from a branch detail view page
        initial_branch_id = request.GET.get("branch")
        # Initialize form variables. If branch ID was supplied in GET query params, pre-select it
        initial_data = {"branch": initial_branch_id} if initial_branch_id else {}
        # Instantiate form scoping it to the user's branch permissions
        form = ProductForm(user=request.user, initial=initial_data)
        
        # Instantiate the bulk formset
        is_global = has_global_inventory_access(request.user)
        formset = self.ProductFormSet(
            queryset=Product.objects.none(),
            form_kwargs={"user": request.user},
        )

        # Render the add_product template and pass the scoped context
        return render(
            request,
            "products/add_product.html",
            {
                "form": form,
                "formset": formset,
                "is_global": is_global,
                "active_tab": "single",
            },
        )

    def post(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            # Redirect to log-in screen if not logged in
            return redirect("accounts:login")
        
        # Check if user clicked bulk import submit button instead of single manual entry
        form_type = request.POST.get("form_type")
        
        # Delegate request according to the form type
        if form_type == "bulk":
            return self.handle_bulk_upload(request)
        elif form_type == "online_bulk":
            return self.handle_online_bulk_upload(request)
            
        # Standard manual single product creation
        # Instantiate the form using POST body data and uploaded files (for images/datasheets)
        form = ProductForm(request.POST, request.FILES, user=request.user)
        # Validate form constraints, checking required fields and correct data types
        if form.is_valid():
            # Build database record but do not write yet (commit=False) to allow manual field adjustments
            product = form.save(commit=False)
            # Associate the currently logged-in user as the creator of this catalog record
            product.created_by = request.user
            
            # Enforce branch isolation rules if the user is not a global administrator
            if not has_global_inventory_access(request.user):
                # Restrict the product to the staff user's own home branch to prevent cross-branch insertions
                product.branch = request.user.branch
            # Otherwise, allow Super Admins/Global managers to select any branch from form dropdown selection
            if form.cleaned_data.get("branch"):
                product.branch = form.cleaned_data.get("branch")
            
            # Save the Product master catalog item to write it to the database
            product.save()
            
            # Automatically establish stock tracking row in BranchStock for the designated branch
            # Use get_or_create to prevent duplicate stocks for the same product and branch
            BranchStock.objects.get_or_create(
                product=product,
                branch=product.branch or request.user.branch,
                defaults={
                    # Assign the shelf/rack locations entered on the UI virtual fields
                    "rack_number": form.cleaned_data.get("rack_number", "-"),
                    "shelf_number": form.cleaned_data.get("shelf_number", "-"),
                    "local_sku": form.cleaned_data.get("local_sku"),
                },
            )
            
            # Log action to audit records for security and action tracing
            AuditLog.log(request.user, "created", product)
            # Display a friendly success message to the front-end user
            messages.success(request, f"Product '{product.name}' added successfully!")
            # Redirect back to the central product catalog listings page
            return redirect("products")
            
        # If form is invalid, re-render the form with validation errors displayed next to fields
        is_global = has_global_inventory_access(request.user)
        formset = self.ProductFormSet(
            queryset=Product.objects.none(),
            form_kwargs={"user": request.user},
        )
        return render(
            request,
            "products/add_product.html",
            {
                "form": form,
                "formset": formset,
                "is_global": is_global,
                "active_tab": "single",
            },
        )

    def handle_online_bulk_upload(self, request):
        is_global = has_global_inventory_access(request.user)
        formset = self.ProductFormSet(
            request.POST,
            queryset=Product.objects.none(),
            form_kwargs={"user": request.user},
        )
        if formset.is_valid():
            saved_count = 0
            for form in formset:
                # Skip blank rows or rows marked for deletion
                if form.cleaned_data.get("name") and not form.cleaned_data.get("DELETE"):
                    product = form.save(commit=False)
                    product.created_by = request.user
                    
                    if not is_global:
                        product.branch = request.user.branch
                    else:
                        if form.cleaned_data.get("branch"):
                            product.branch = form.cleaned_data.get("branch")
                            
                    product.save()
                    
                    # Manage virtual fields mapping to BranchStock
                    initial_quantity = form.cleaned_data.get("initial_quantity") or 0
                    rack_number = form.cleaned_data.get("rack_number") or "-"
                    shelf_number = form.cleaned_data.get("shelf_number") or "-"
                    local_sku = form.cleaned_data.get("local_sku") or product.sku
                    
                    target_branch = product.branch or request.user.branch
                    if target_branch:
                        bs, _ = BranchStock.objects.get_or_create(
                            product=product,
                            branch=target_branch,
                        )
                        bs.rack_number = rack_number
                        bs.shelf_number = shelf_number
                        bs.local_sku = local_sku
                        bs.current_quantity = initial_quantity
                        bs.save()
                        
                    AuditLog.log(request.user, "created", product)
                    saved_count += 1
            
            messages.success(request, f"Successfully created {saved_count} products!")
            return redirect("products")
        else:
            # Gather errors to alert the user
            error_msgs = []
            for i, form_errors in enumerate(formset.errors):
                if form_errors:
                    err_details = []
                    for k, v in form_errors.items():
                        # Resolve human-readable field names if possible
                        field = formset.forms[i].fields.get(k)
                        field_label = field.label if field and field.label else k.replace("_", " ").title()
                        err_details.append(f"{field_label}: {v[0]}")
                    error_msgs.append(f"Row {i+1}: {', '.join(err_details)}")
            
            messages.warning(request, "Please correct the errors in the grid below.")
            if error_msgs:
                for err in error_msgs[:5]:
                    messages.error(request, err)
                    
            # Re-render with validation errors and set active tab to online_bulk
            form = ProductForm(user=request.user)
            return render(
                request,
                "products/add_product.html",
                {
                    "form": form,
                    "formset": formset,
                    "is_global": is_global,
                    "active_tab": "online_bulk",
                },
            )

    def handle_bulk_upload(self, request):
        """
        Parses imported Excel spreadsheet files, matches categories/branches, 
        extracts attached ZIP datasheet documents, and creates corresponding database records.
        """
        # Fetch the uploaded spreadsheet file from request files list
        excel_file = request.FILES.get("excel_file")
        # Fetch the optional ZIP archive containing PDF/document datasheets
        datasheet_zip = request.FILES.get("datasheet_zip")
        # Check if the user opted to bypass/skip rows that match existing SKU identifiers
        skip_duplicates = request.POST.get("skip_duplicates") == "on"
        
        # Enforce that a file must be selected before processing
        if not excel_file:
            messages.error(request, "Please select an Excel file to upload.")
            return redirect("add-product")
            
        # Restrict size to prevent memory overflows on server (max 5 megabytes allowed)
        if excel_file.size > 5 * 1024 * 1024:
            messages.error(request, "File size must be less than 5MB.")
            return redirect("add-product")
            
        try:
            # Parse Excel structure using pandas, checking extension to choose engine
            df = (
                pd.read_excel(excel_file, engine="openpyxl")
                if excel_file.name.endswith(".xlsx")
                else pd.read_excel(excel_file, engine="xlrd")
            )
            
            # Validate required sheet columns to ensure compatibility
            required_columns = ["Name"]
            # Detect any missing columns in the sheet
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(
                    request, f"Missing required columns: {', '.join(missing_columns)}"
                )
                return redirect("add-product")
                
            # Initialize counters to summarize the import job results
            success_count, error_count, skipped_count, errors = 0, 0, 0, []
            zip_files = {}
            
            # If a ZIP archive with datasheets is uploaded, extract it to a memory lookup map
            if datasheet_zip:
                try:
                    # Open the ZIP archive for reading file contents in-memory
                    with zipfile.ZipFile(datasheet_zip) as zf:
                        # Iterate through each file entry packed in the ZIP archive
                        for name in zf.namelist():
                            # Store the file's raw binary data in a lookup dictionary keyed by its filename
                            zip_files[name] = zf.read(name)
                except Exception as e:
                    # Capture and handle invalid or corrupted ZIP archives
                    messages.error(request, f"Error reading datasheet ZIP: {e}")
                    return redirect("add-product")
                    
            # Iterate through rows inside the uploaded Excel sheet using Pandas iterrows()
            for index, row in df.iterrows():
                try:
                    # Clean and extract parameters from current sheet row
                    name = str(row["Name"]).strip() if not pd.isna(row.get("Name")) else ""
                    sku = str(row["SKU"]).strip() if not pd.isna(row.get("SKU")) else None
                    if not sku:
                        sku = None

                    serial_number = str(row["Serial Number"]).strip() if not pd.isna(row.get("Serial Number")) else None
                    if not serial_number:
                        serial_number = None

                    shelf_number = str(row["Shelf Number"]).strip() if not pd.isna(row.get("Shelf Number")) else "-"
                    description = str(row["Description"]).strip() if not pd.isna(row.get("Description")) else ""
                    
                    # Validate empty name constraint
                    if not name:
                        error_count += 1
                        errors.append(f"Row {index + 2}: Missing required field 'Name'")
                        continue

                        
                    # Check for duplicate global SKU identifiers in the database (only if SKU is provided)
                    existing_product = Product.objects.filter(sku=sku).first() if sku else None
                            
                    # Resolve category linkage by querying the category name from Category table
                    category = None
                    if "Category" in df.columns and not pd.isna(row["Category"]):
                        cat_name = str(row["Category"]).strip()
                        if cat_name:
                            category = Category.objects.filter(
                                name__iexact=cat_name
                            ).first()
                            if not category:
                                category = Category.objects.create(name=cat_name)
                        
                    # Resolve target branch assignment by matching the branch code
                    target_branch = None
                    if "Branch (Code)" in df.columns and not pd.isna(row["Branch (Code)"]):
                        target_branch = Branch.objects.filter(
                            code__iexact=str(row["Branch (Code)"]).strip()
                        ).first()
                    
                    # If branch is not specified, default to the uploader's home branch
                    if not target_branch and hasattr(request.user, "branch"):
                        target_branch = request.user.branch
                        
                    # Pull matching datasheet file content from ZIP archive if present
                    datasheet_file = None
                    if (
                        "Datasheet Filename" in df.columns
                        and not pd.isna(row.get("Datasheet Filename"))
                    ):
                        fn = str(row["Datasheet Filename"]).strip()
                        if fn in zip_files:
                            datasheet_file = ContentFile(zip_files[fn], name=fn)

                    brand = str(row.get("Brand", "")).strip() if "Brand" in df.columns and not pd.isna(row.get("Brand")) else ""
                    model_number = str(row.get("Model Number", "")).strip() if "Model Number" in df.columns and not pd.isna(row.get("Model Number")) else ""
                    rack_number = str(row.get("Rack Number", "-")).strip() if "Rack Number" in df.columns and not pd.isna(row.get("Rack Number")) else "-"
                    local_sku = str(row.get("Local SKU", sku)).strip() if "Local SKU" in df.columns and not pd.isna(row.get("Local SKU")) else sku
                    
                    quantity = 0
                    if "Quantity" in df.columns and not pd.isna(row.get("Quantity")):
                        try:
                            quantity = max(0, int(row["Quantity"]))
                        except ValueError:
                            pass
                            
                    if existing_product:
                        # Update existing product (anything can be uploaded multiple times to update)
                        existing_product.name = name
                        existing_product.category = category
                        existing_product.brand = brand
                        existing_product.model_number = model_number
                        existing_product.description = description
                        existing_product.serial_number = serial_number
                        if datasheet_file:
                            existing_product.datasheet = datasheet_file
                        existing_product.save()
                        product = existing_product
                        skipped_count += 1  # Used to track the updated duplicate products count
                    else:
                        # Create the Product record in database
                        product = Product.objects.create(
                            name=name,
                            sku=sku,
                            category=category,
                            branch=target_branch,
                            created_by=request.user,
                            datasheet=datasheet_file,
                            brand=brand,
                            model_number=model_number,
                            description=description,
                            serial_number=serial_number,
                        )
                        success_count += 1
                    
                    # Create or update BranchStock entry to track quantities in that branch location
                    if target_branch:
                        bs, _ = BranchStock.objects.get_or_create(
                            product=product,
                            branch=target_branch,
                        )
                        bs.rack_number = rack_number
                        bs.shelf_number = shelf_number
                        bs.local_sku = local_sku
                        bs.current_quantity = quantity
                        bs.save()
                        
                    # Add audit trace log
                    AuditLog.log(request.user, "updated" if existing_product else "created", product)
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
                    
            # Provide feedback alerts based on results to update the UI message queue
            if success_count > 0:
                messages.success(
                    request, f"Successfully imported {success_count} new products!"
                )
            if skipped_count > 0:
                messages.warning(
                    request, f"Warning: {skipped_count} existing products with matching SKUs were updated/overridden with the uploaded data."
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
    """
    Renders list view of product stock levels, scoped by user branch permissions.
    """
    def get(self, request):
        # Verify user login status
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        # Determine if the user has global permission to view all branches
        is_global = has_global_inventory_access(request.user)
        # Fetch user's home branch membership
        user_branch = getattr(request.user, "branch", None)
        
        # Select related fields in advance to avoid 1+N database querying
        qs = BranchStock.objects.select_related(
            "product", "branch", "product__category", "product__created_by"
        )
        
        # Scrutinize branch boundaries: Non-global users can only see their own branch stocks
        if not is_global and user_branch:
            # Filter the queryset to the user's home branch
            qs = qs.filter(branch=user_branch)
        elif not is_global:
            # If they are not global and don't belong to any branch, return empty result set
            qs = qs.none()
            
        # Apply search string matching across SKUs, names, brands, shelves, and serials
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
            
        # Apply drop-down filters dynamically if selected in UI
        category_id = request.GET.get("category")
        if category_id:
            qs = qs.filter(product__category_id=category_id)
            
        branch_id = request.GET.get("branch")
        if branch_id and is_global:
            qs = qs.filter(branch_id=branch_id)
            
        status = request.GET.get("status")
        if status:
            qs = qs.filter(product__status=status)
            
        # Apply column ordering based on query param sort key
        sort_by = request.GET.get("sort", "-product__created_at")
        qs = qs.order_by(sort_by)
        
        # Paginate results with 25 products per page
        paginator = Paginator(qs, 25)
        # Fetch the active page requested
        page_obj = paginator.get_page(request.GET.get("page"))
        
        # Flatten structure: copy properties from BranchStock onto cloned Product models.
        # This keeps templates simple as they can reference product.rack_number, etc.
        cloned_products = []
        for bs in page_obj:
            # Deep clone the master product object
            p = copy.copy(bs.product)
            # Inject branch stock properties directly into the clone
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
                0,
            )
            cloned_products.append(p)
            
        # Re-assign the modified list to the paginator object
        page_obj.object_list = cloned_products
        
        # Render the template passing the compiled variables
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
    """
    Renders product item parameters page (GET) and processes manual stock adjustments (POST).
    """
    def get(self, request, pk):
        # Verify user login status
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        from stock.models import StockEntry
        from inventory.models import Rental

        # Retrieve product or return HTTP 404
        product = get_object_or_404(Product, pk=pk)
        # Check global access rights of the current active user
        is_global = has_global_inventory_access(request.user)
        # Fetch user's home branch membership
        user_branch = getattr(request.user, "branch", None)
        # Fetch the selected branch query parameter (used by admins)
        priority_branch_id = request.GET.get("branch")
        
        # Sum quantities across branches to get global totals (restrict to home branch for local staff)
        total_display_stock = (
            BranchStock.objects.filter(
                product=product, **({} if is_global else {"branch": user_branch})
            ).aggregate(Sum("current_quantity"))["current_quantity__sum"]
            or 0
        )
        
        # Get list of branch stocks
        branch_stocks = BranchStock.objects.filter(product=product).select_related(
            "branch"
        )
        if not is_global:
            # Non-global users can only view stock matching their own branch
            branch_stocks = (
                branch_stocks.filter(branch=user_branch)
                if user_branch
                else branch_stocks.none()
            )
            
        # Select highlighted stock details for quick adjustments pane
        highlighted_stock, highlighted_info = 0, {
            "rack": "-",
            "shelf": "-",
            "branch_name": "N/A",
        }
        # Determine target branch for quick adjustment
        target_branch = (
            Branch.objects.filter(id=priority_branch_id).first()
            if priority_branch_id and is_global
            else user_branch
        )
        if target_branch:
            # Query BranchStock for the resolved target branch
            lb = BranchStock.objects.filter(
                product=product, branch=target_branch
            ).first()
            if lb:
                # Assign values to be rendered in the adjustments pane
                highlighted_stock, highlighted_info = lb.current_quantity, {
                    "rack": lb.rack_number or "-",
                    "shelf": lb.shelf_number or "-",
                    "branch_name": target_branch.name,
                }
                
        # Query product rentals log scoped by branch if needed
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
                # Fetch recent stock entry transaction history logs for this product
                "recent_stock_entries": filter_by_branch(
                    StockEntry.objects.filter(product=product), request.user
                ).order_by("-timestamp")[:10],
                "is_global": is_global,
                "branches": Branch.objects.all() if is_global else [],
            },
        )

    def post(self, request, pk):
        # Fetch product within branch isolation bounds to prevent unauthorized stock tampering
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        
        # Handle manual inventory increment/decrement adjustments from detail page
        if request.POST.get("action") == "stock_adjustment":
            # Check permissions: must be an admin or have can_manage_adjustments permission
            if not getattr(request.user, "is_admin", False) and not getattr(request.user, "can_manage_adjustments", False):
                messages.error(request, "You do not have permission to make stock adjustments.")
                return redirect("product-detail", pk=pk)
            # Extract form variables for adjustment type (e.g. addition/subtraction), quantity, and reason
            adj_type, qty, reason = (
                request.POST.get("adjustment_type"),
                int(request.POST.get("quantity", 0)),
                request.POST.get("reason", "Manual adjustment from detail page"),
            )
            # Enforce that adjustment quantity must be a positive integer
            if qty > 0:
                # Determine target branch. Super admins can adjust stock for any branch;
                # branch staff are strictly limited to their own branch.
                target_branch = (
                    Branch.objects.filter(id=request.POST.get("branch")).first()
                    if request.POST.get("branch") and request.user.is_super_admin
                    else (getattr(request.user, "branch", None) or product.branch)
                )
                from stock.models import StockEntry

                # Ensure a stock record row exists in the database for the target branch
                bs, _ = BranchStock.objects.get_or_create(
                    product=product, branch=target_branch
                )
                
                # Write a stock entry log to the database.
                # Crucial detail: Saving a StockEntry automatically triggers a signals receiver 
                # that updates the corresponding BranchStock.current_quantity field.
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
                # Display success notification on UI
                messages.success(request, f"Stock {adj_type} recorded successfully.")
            else:
                # Render validation error if quantity input was invalid
                messages.error(request, "Invalid quantity.")
                
        # Redirect back to the product details view page
        return redirect("product-detail", pk=pk)


@method_decorator(branch_admin_required, name="dispatch")
class ProductEditView(View):
    """
    Renders edit product form (GET) and processes edits (POST).
    """
    def get(self, request, pk):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Retrieve product record within branch isolation rules (prevents users editing other branch items)
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        # Render the edit page passing the instance and user context to populate branch options
        return render(
            request,
            "products/edit_product.html",
            {
                "form": ProductForm(instance=product, user=request.user),
                "product": product,
            },
        )

    def post(self, request, pk):
        # Retrieve product record within branch isolation rules (fails with 404 if accessed by wrong branch staff)
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        # Construct the ProductForm using POST data, files, instance, and user details
        form = ProductForm(
            request.POST, request.FILES, instance=product, user=request.user
        )
        # Run form validation rules
        if form.is_valid():
            # Block branch tampering for non-global staff users by restoring original product branch assignment
            if not has_global_inventory_access(request.user):
                form.instance.branch = product.branch
                
            # Save the updated product data to the DB
            updated_product = form.save()
            
            # Determine update branch mapping
            update_branch = (
                request.user.branch
                if not has_global_inventory_access(request.user)
                and getattr(request.user, "branch", None)
                else updated_product.branch
            )
            
            # Synchronize location fields (Rack, Shelf, Local SKU) from virtual fields to BranchStock record
            if update_branch:
                # Resolve the matching stock tracking row
                bs, _ = BranchStock.objects.get_or_create(
                    product=updated_product, branch=update_branch
                )
                # Apply the clean form inputs and update the stock record
                bs.rack_number, bs.shelf_number, bs.local_sku = (
                    form.cleaned_data.get("rack_number") or "-",
                    form.cleaned_data.get("shelf_number") or "-",
                    form.cleaned_data.get("local_sku"),
                )
                bs.save()
                
            # Log the edit action to AuditLog for security tracking
            AuditLog.log(request.user, "updated", updated_product)
            # Display success message to user
            messages.success(
                request, f"Product {updated_product.name} updated successfully!"
            )
            # Redirect back to the products catalog index
            return redirect("products")
            
        # If the form failed validation, collect error messages and put them in request messages
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")
        # Re-render the edit page template with errors and current form state
        return render(
            request, "products/edit_product.html", {"form": form, "product": product}
        )


@method_decorator(super_admin_required, name="dispatch")
class ProductDeleteView(View):
    """
    Handles permanent deletion of product catalog items.
    """
    def post(self, request, pk):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Ensure the item exists and belongs to the allowed branch bounds
        product = get_object_or_404(get_isolated_products(request.user), pk=pk)
        product_name = product.name
        # Delete item (which triggers cascade deletions of dependent records like BranchStocks in the DB)
        product.delete()
        # Log deletion trace to database audit tables
        AuditLog.log(request.user, "deleted", None, f"Deleted product: {product_name}")
        # Show success alert message
        messages.success(request, f"Product '{product_name}' has been deleted.")
        # Redirect back to products page
        return redirect("products")


@method_decorator(super_admin_required, name="dispatch")
class ProductBulkDeleteView(View):
    """
    Handles bulk deletion of multiple product catalog items at once.
    Restricted to Super Admins.
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        
        product_ids = request.POST.getlist("product_ids")
        if not product_ids:
            messages.warning(request, "No products selected for deletion.")
            return redirect("products")
            
        products_to_delete = get_isolated_products(request.user).filter(id__in=product_ids)
        deleted_count = products_to_delete.count()
        
        if deleted_count > 0:
            product_names = ", ".join([p.name for p in products_to_delete])
            products_to_delete.delete()
            AuditLog.log(request.user, "deleted", None, f"Bulk deleted {deleted_count} products: {product_names}")
            messages.success(request, f"Successfully deleted {deleted_count} products.")
        else:
            messages.error(request, "No valid products found to delete.")
            
        return redirect("products")
