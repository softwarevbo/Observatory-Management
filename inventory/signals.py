from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Sum
from stock.models import StockEntry
from .models import BranchStock, InventoryAdjustment

"""
This module contains signal receivers that trigger stock recalculations.
Ensures that BranchStock levels are dynamically computed from StockEntry and InventoryAdjustment histories.
"""


def recalculate_branch_stock(product, branch):
    """
    Recalculates the current quantity for a specific product at a specific branch.
    Aggregates all relevant StockEntry and InventoryAdjustment quantities.
    """
    if not product or not branch:
        return

    branch_stock, _ = BranchStock.objects.get_or_create(branch=branch, product=product)

    from django.apps import apps

    StockEntryModel = apps.get_model("stock", "StockEntry")

    # Sum of all stock in entries
    stock_in = (
        StockEntryModel.objects.filter(
            product=product, branch=branch, entry_type="in"
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    # Sum of all stock out entries
    stock_out = (
        StockEntryModel.objects.filter(
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
    """
    Stores the old branch and product reference before saving a StockEntry.
    Enables recalculation for both old and new targets if they are updated.
    """
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
    """
    Triggers stock level updates after a StockEntry is created, modified, or deleted.
    Updates both current and legacy branch/product targets if changed.
    """
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
    """
    Stores the old branch and product reference before saving an InventoryAdjustment.
    Enables recalculation for both old and new targets if they are updated.
    """
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
    """
    Triggers stock level updates after an InventoryAdjustment is created, modified, or deleted.
    Updates both current and legacy branch/product targets if changed.
    """
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
