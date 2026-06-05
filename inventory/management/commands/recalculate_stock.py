from django.core.management.base import BaseCommand
from inventory.models import BranchStock, Branch
from products.models import Product
from inventory.signals import recalculate_branch_stock

"""
This module contains the recalculate_stock Django custom administrative management command.
Allows administrative recalculations of Branch Stock from StockEntry and InventoryAdjustment listings.
"""


class Command(BaseCommand):
    """
    Recalculates all branch stock quantities based on StockEntry and InventoryAdjustment records.
    """
    help = "Recalculates all branch stock quantities based on StockEntry and InventoryAdjustment records."

    def handle(self, *args, **options):
        self.stdout.write("Starting stock recalculation...")

        # Get all combinations of products and branches that have stock records
        branch_stocks = BranchStock.objects.all()
        total = branch_stocks.count()

        for i, bs in enumerate(branch_stocks):
            recalculate_branch_stock(bs.product, bs.branch)
            if (i + 1) % 10 == 0:
                self.stdout.write(f"Processed {i + 1}/{total} records...")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully recalculated {total} stock records.")
        )
