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

"""
This module processes view controllers for product catalog creation, updates, deletion,
searches, and bulk spreadsheet imports.
"""


@method_decorator(staff_permission_required("can_add_inventory"), name="dispatch")
class ProductCreateView(View):
    """
    Handles rendering the product entry form (GET) and processing single/bulk product uploads (POST).
    """
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
        # Render the add_product template and pass the scoped form context
        return render(request, "products/add_product.html", {"form": form})

    def post(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            # Redirect to log-in screen if not logged in
            return redirect("accounts:login")
        
        # Check if user clicked bulk import submit button instead of single manual entry
        form_type = request.POST.get("form_type")
        # If form type is bulk, delegate the request to handle_bulk_upload helper method
        if form_type == "bulk":
            return self.handle_bulk_upload(request)
            
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
        return render(request, "products/add_product.html", {"form": form})

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
            required_columns = ["Name", "SKU", "Price"]
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
                    
            # Map products database to lowercased name keys to speed up category lookups
            products = {p.name.lower(): p for p in Product.objects.all()}
            
            # Iterate through rows inside the uploaded Excel sheet using Pandas iterrows()
            for index, row in df.iterrows():
                try:
                    # Clean and extract Name, SKU, and Price parameters from current sheet row
                    name = str(row["Name"]).strip()
                    sku = str(row["SKU"]).strip()
                    price = float(row["Price"])
                    
                    # Validate empty constraints to verify all required fields are present
                    if not name or not sku or pd.isna(price):
                        error_count += 1
                        # Save the row number (1-indexed, adding 2 for header offset) for reporting
                        errors.append(f"Row {index + 2}: Missing required fields")
                        continue
                        
                    # Check for duplicate global SKU identifiers in the database
                    if Product.objects.filter(sku=sku).exists():
                        # If skip_duplicates checkbox was checked, simply bypass the duplicate row
                        if skip_duplicates:
                            skipped_count += 1
                            continue
                        else:
                            # Otherwise, treat duplicate SKU as a validation error and abort row creation
                            error_count += 1
                            errors.append(
                                f'Row {index + 2}: SKU "{sku}" already exists'
                            )
                            continue
                            
                    # Resolve category linkage by querying the category name from Category table
                    category = None
                    if "Category" in df.columns and not pd.isna(row["Category"]):
                        category = Category.objects.filter(
                            name__iexact=str(row["Category"]).strip()
                        ).first()
                        
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
                        # If the ZIP directory holds a matching file name, read it
                        if fn in zip_files:
                            # Convert the in-memory binary block into a Django-compatible ContentFile
                            datasheet_file = ContentFile(zip_files[fn], name=fn)
                            
                    # Create the Product record in database with the resolved parameters
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
                    
                    # Create a BranchStock entry to track quantities in that branch location
                    if target_branch:
                        BranchStock.objects.get_or_create(
                            product=product,
                            branch=target_branch,
                            defaults={
                                # Map optional rack/shelf and local SKU parameters
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
                        
                    # Add record creation audit trace log to track action history
                    AuditLog.log(request.user, "created", product)
                    # Increment count of successfully imported records
                    success_count += 1
                except Exception as e:
                    # Increment failed count and capture the error message details
                    error_count += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
                    
            # Provide feedback alerts based on results to update the UI message queue
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
                bs.current_quantity * (p.price or 0),
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


class ProductDeleteView(View):
    """
    Handles permanent deletion of product catalog items.
    Restricted to super administrators via @admin_required.
    """
    @method_decorator(admin_required)
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
