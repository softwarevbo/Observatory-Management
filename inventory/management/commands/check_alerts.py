from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from inventory.models import Alert, QuantityLimit, BranchStock, Branch
from products.models import Product
from stock.models import StockEntry

"""
This module contains the check_alerts Django custom administrative management command.
Monitors product stock levels against quantity limits by branch and fires alerts.
"""


class Command(BaseCommand):
    """
    Check product quantities by branch and create alerts when limits are reached.
    """
    help = (
        "Check product quantities by branch and create alerts when limits are reached"
    )

    def handle(self, *args, **options):
        self.stdout.write("Checking product quantities and limits by branch...")

        alerts_created = 0
        alerts_updated = 0

        # Check Specific Quantity Limits
        limits = QuantityLimit.objects.filter(is_active=True)
        for limit in limits:
            product = limit.product
            branch = limit.branch

            if not branch:
                # If limit has no branch, it's a global limit? Or we apply to all branches?
                # Usually standard limits are global, but QuantityLimit model has branch.
                # If branch is null, we skip or apply to all?
                # Let's skip for now or treat as unassigned.
                continue

            # Use BranchStock as source of truth
            bs = BranchStock.objects.filter(product=product, branch=branch).first()
            current_quantity = bs.current_quantity if bs else 0

            # Check if quantity is at or below limit
            if current_quantity <= limit.limit_quantity:
                # Check if there's already an active alert for this product and limit at this branch
                existing_alert = Alert.objects.filter(
                    product=product,
                    branch=branch,
                    alert_type="limit_reached",
                    status="active",
                ).first()

                if existing_alert:
                    # Update existing alert if quantity changed
                    if existing_alert.current_quantity != current_quantity:
                        existing_alert.current_quantity = current_quantity
                        existing_alert.message = f"[{branch.code}] Product {product.name} quantity ({current_quantity}) has reached or fallen below the limit of {limit.limit_quantity}"
                        existing_alert.save()
                        alerts_updated += 1
                else:
                    # Create new alert
                    Alert.objects.create(
                        product=product,
                        branch=branch,
                        alert_type="limit_reached",
                        status="active",
                        message=f"[{branch.code}] Product {product.name} quantity ({current_quantity}) has reached or fallen below the limit of {limit.limit_quantity}",
                        current_quantity=current_quantity,
                        limit_quantity=limit.limit_quantity,
                    )
                    alerts_created += 1
            else:
                # Check if there's an active alert that should be resolved
                existing_alert = Alert.objects.filter(
                    product=product,
                    branch=branch,
                    alert_type="limit_reached",
                    status="active",
                ).first()

                if existing_alert:
                    existing_alert.status = "resolved"
                    existing_alert.resolved_at = timezone.now()
                    existing_alert.message = f"[{branch.code}] Alert resolved: {product.name} quantity ({current_quantity}) is now above limit ({limit.limit_quantity})"
                    existing_alert.save()

        # Check Out of Stock by Branch
        branch_stocks = BranchStock.objects.all()
        for bs in branch_stocks:
            product = bs.product
            branch = bs.branch
            current_quantity = bs.current_quantity

            if current_quantity <= 0:
                # Check if there's already an active out of stock alert for this branch
                existing_alert = Alert.objects.filter(
                    product=product,
                    branch=branch,
                    alert_type="out_of_stock",
                    status="active",
                ).first()

                if not existing_alert:
                    Alert.objects.create(
                        product=product,
                        branch=branch,
                        alert_type="out_of_stock",
                        status="active",
                        message=f"[{branch.code}] Product {product.name} is out of stock",
                        current_quantity=current_quantity,
                    )
                    alerts_created += 1
            else:
                # Resolve out of stock alert if quantity is now positive
                existing_alert = Alert.objects.filter(
                    product=product,
                    branch=branch,
                    alert_type="out_of_stock",
                    status="active",
                ).first()

                if existing_alert:
                    existing_alert.status = "resolved"
                    existing_alert.resolved_at = timezone.now()
                    existing_alert.message = f"[{branch.code}] Out of stock alert resolved: {product.name} now has {current_quantity} in stock"
                    existing_alert.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Branch-aware alert check completed. Created: {alerts_created}, Updated: {alerts_updated}"
            )
        )
