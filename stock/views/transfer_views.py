from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.db.models import Q
from django.utils import timezone

from audit.models import AuditLog
from inventory.models import Branch, BranchStock
from inventory.notifications import notify_inventory_admins
from inventory.utils import has_global_inventory_access
from products.models import Product
from ..models import StockEntry, StockTransfer


class StockTransferPageView(View):
    """
    Handles stock transfer requests, including transfers in-transit.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        # Determine visibility scope: super admins see all transfers, branch staff see branch-specific ones
        transfers = (
            StockTransfer.objects.all().select_related(
                "product", "from_branch", "to_branch"
            )
            if request.user.is_super_admin
            else StockTransfer.objects.filter(
                Q(from_branch=request.user.branch) | Q(to_branch=request.user.branch)
            ).select_related("product", "from_branch", "to_branch")
        )
        transfers = transfers.order_by("-created_at")
        
        # Check permissions for inventory access
        is_global, user_branch = has_global_inventory_access(request.user), getattr(
            request.user, "branch", None
        )
        
        # Retrieve active stock levels
        bs_qs = BranchStock.objects.filter(current_quantity__gt=0).select_related(
            "product", "branch"
        )
        if not is_global and user_branch:
            bs_qs = bs_qs.filter(branch=user_branch)
            
        transfer_products = [
            {
                "id": bs.product.id,
                "name": bs.product.name,
                "sku": bs.product.sku or "",
                "branch_name": bs.branch.name,
                "branch_id": bs.branch.id,
                "quantity": bs.current_quantity,
            }
            for bs in bs_qs
        ]
        
        # Paginate results
        paginator = Paginator(transfers, 50)
        page_obj = paginator.get_page(request.GET.get("page"))
        return render(
            request,
            "stock/stock_transfer.html",
            {
                "transfers": page_obj,
                "page_obj": page_obj,
                "transfer_products": transfer_products,
                "branches": Branch.objects.filter(is_active=True),
            },
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        # Extract form parameters
        product_id, from_branch_id, to_branch_id, quantity, description = (
            request.POST.get("product_id"),
            request.POST.get("from_branch"),
            request.POST.get("to_branch"),
            int(request.POST.get("quantity", 0)),
            request.POST.get("description", ""),
        )
        
        # Prevent self-transfers
        if from_branch_id == to_branch_id:
            messages.error(
                request, "Source and destination branches cannot be the same."
            )
            return redirect("stock-transfer-page")
            
        # Verify inputs and objects
        product, from_branch, to_branch = (
            get_object_or_404(Product, id=product_id),
            get_object_or_404(Branch, id=from_branch_id),
            get_object_or_404(Branch, id=to_branch_id),
        )
        
        # Verify source branch stock levels
        source_stock = BranchStock.objects.filter(
            product=product, branch=from_branch
        ).first()
        if not source_stock or source_stock.current_quantity < quantity:
            messages.error(request, f"Insufficient stock at {from_branch.name}.")
            return redirect("stock-transfer-page")
            
        # Register a stock out entry representing transfer transit status
        StockEntry.objects.create(
            product=product,
            branch=from_branch,
            quantity=quantity,
            entry_type="out",
            description=f"Transfer to {to_branch.name} (Pending). {description}",
            created_by=request.user,
        )
        
        # Create persistent StockTransfer record
        transfer = StockTransfer.objects.create(
            product=product,
            from_branch=from_branch,
            to_branch=to_branch,
            quantity=quantity,
            notes=description,
            created_by=request.user,
            status="pending",
        )
        
        # Notify destination and inventory administrators
        notify_inventory_admins(
            request.user,
            "stock_transfer",
            f"New Transfer Inbound: {product.name}",
            f"{quantity} units of {product.name} are in transit from {from_branch.name}.",
            target_url="/inventory/stock/transfer/",
        )
        
        # Record security audit log
        AuditLog.log(
            request.user,
            "transfer_initiated",
            product,
            f"Initiated transfer of {quantity} to {to_branch.name}",
        )
        messages.success(
            request,
            f"Transfer initiated. {quantity} units are now in transit to {to_branch.name}.",
        )
        return redirect("stock-transfer-page")


class StockTransferReceiveView(View):
    """
    View to process reception of pending inbound transfers at destination branch.
    """
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        transfer = get_object_or_404(StockTransfer, pk=pk)
        
        # Prevent double-processing
        if transfer.status != "pending":
            messages.error(request, "This transfer has already been processed.")
            return redirect("stock-transfer-page")
            
        # Authorize: user branch must match target destination branch unless super admin
        if (
            not request.user.is_super_admin
            and request.user.branch != transfer.to_branch
        ):
            messages.error(request, "You are not authorized.")
            return redirect("stock-transfer-page")
            
        rack, shelf, sku = (
            request.POST.get("rack_number"),
            request.POST.get("shelf_number"),
            request.POST.get("sku"),
        )
        if not rack or not shelf:
            messages.error(request, "Please provide Rack and Shelf locations.")
            return redirect("stock-transfer-page")
            
        product = transfer.product
        
        # Update transfer state
        (
            transfer.status,
            transfer.rack_number,
            transfer.shelf_number,
            transfer.received_at,
            transfer.received_by,
        ) = ("received", rack, shelf, timezone.now(), request.user)
        transfer.save()
        
        # Update destination BranchStock levels and location details
        bs, _ = BranchStock.objects.get_or_create(
            product=product, branch=transfer.to_branch
        )
        bs.rack_number, bs.shelf_number = rack, shelf
        if sku:
            bs.local_sku = sku
        bs.save()
        
        # Create an incoming stock entry to finalize the transaction
        StockEntry.objects.create(
            product=product,
            branch=transfer.to_branch,
            quantity=transfer.quantity,
            entry_type="in",
            description=f"Received transfer from {transfer.from_branch.name}. Location: {rack}/{shelf}",
            created_by=request.user,
        )
        
        # Record security audit log entry
        AuditLog.log(
            request.user,
            "transfer_received",
            product,
            f"Received {transfer.quantity} at {transfer.to_branch.name}. Local SKU: {sku}, Loc: {rack}/{shelf}",
        )
        messages.success(
            request,
            f"Successfully received {transfer.quantity} units of {product.name}.",
        )
        return redirect("stock-transfer-page")
