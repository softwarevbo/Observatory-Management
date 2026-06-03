from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Sum
from stock.models import StockEntry
from .models import BranchStock, InventoryAdjustment


def recalculate_branch_stock(product, branch):
    """
    Recalculates the current quantity for a specific product at a specific branch.
    """
    if not product or not branch:
        return

    branch_stock, _ = BranchStock.objects.get_or_create(branch=branch, product=product)

    from django.apps import apps

    StockEntry = apps.get_model("stock", "StockEntry")

    # Sum of all stock in entries
    stock_in = (
        StockEntry.objects.filter(
            product=product, branch=branch, entry_type="in"
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    # Sum of all stock out entries
    stock_out = (
        StockEntry.objects.filter(
            product=product, branch=branch, entry_type="out"
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    # Sum of all adjustments (can be positive or negative)
    adjustments = (
        InventoryAdjustment.objects.filter(product=product, branch=branch).aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    # Calculate final quantity
    new_quantity = stock_in + adjustments - stock_out

    # Ensure quantity doesn't go below zero
    branch_stock.current_quantity = max(0, new_quantity)
    branch_stock.save()


@receiver(pre_save, sender=StockEntry)
def capture_old_stock_entry_state(sender, instance, **kwargs):
    """Store old branch/product to recalculate after change."""
    if instance.pk:
        try:
            old_instance = StockEntry.objects.get(pk=instance.pk)
            instance._old_branch = old_instance.branch
            instance._old_product = old_instance.product
        except StockEntry.DoesNotExist:
            instance._old_branch = None
            instance._old_product = None
    else:
        instance._old_branch = None
        instance._old_product = None


@receiver(post_save, sender=StockEntry)
@receiver(post_delete, sender=StockEntry)
def update_stock_on_entry_change(sender, instance, **kwargs):
    """Update branch stock whenever a StockEntry is created, updated, or deleted."""
    # Recalculate for current branch/product
    recalculate_branch_stock(instance.product, instance.branch)

    # If branch or product changed, recalculate for the old one too
    old_branch = getattr(instance, "_old_branch", None)
    old_product = getattr(instance, "_old_product", None)

    if (old_branch and old_branch != instance.branch) or (
        old_product and old_product != instance.product
    ):
        recalculate_branch_stock(
            old_product or instance.product, old_branch or instance.branch
        )


@receiver(pre_save, sender=InventoryAdjustment)
def capture_old_adjustment_state(sender, instance, **kwargs):
    """Store old branch/product to recalculate after change."""
    if instance.pk:
        try:
            old_instance = InventoryAdjustment.objects.get(pk=instance.pk)
            instance._old_branch = old_instance.branch
            instance._old_product = old_instance.product
        except InventoryAdjustment.DoesNotExist:
            instance._old_branch = None
            instance._old_product = None
    else:
        instance._old_branch = None
        instance._old_product = None


@receiver(post_save, sender=InventoryAdjustment)
@receiver(post_delete, sender=InventoryAdjustment)
def update_stock_on_adjustment_change(sender, instance, **kwargs):
    """Update branch stock whenever an InventoryAdjustment is created, updated, or deleted."""
    # Recalculate for current branch/product
    recalculate_branch_stock(instance.product, instance.branch)

    # If branch or product changed, recalculate for the old one too
    old_branch = getattr(instance, "_old_branch", None)
    old_product = getattr(instance, "_old_product", None)

    if (old_branch and old_branch != instance.branch) or (
        old_product and old_product != instance.product
    ):
        recalculate_branch_stock(
            old_product or instance.product, old_branch or instance.branch
        )
