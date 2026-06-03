from django.core.management.base import BaseCommand

from inventory.models import SerialNumber
from products.models import Product


class Command(BaseCommand):
    help = "Sync serial numbers from products to SerialNumber model"

    def handle(self, *args, **options):
        # Get products with serial numbers
        products_with_serials = Product.objects.filter(
            serial_number__isnull=False
        ).exclude(serial_number="")

        self.stdout.write(
            f"Found {products_with_serials.count()} products with serial numbers"
        )

        created_count = 0
        updated_count = 0

        for product in products_with_serials:
            # Check if serial number record already exists
            existing_serial = SerialNumber.objects.filter(
                serial_number=product.serial_number
            ).first()

            if existing_serial:
                # Update existing record if product reference is different
                if existing_serial.product != product:
                    existing_serial.product = product
                    existing_serial.save()
                    updated_count += 1
                    self.stdout.write(
                        f"Updated: {product.serial_number} -> {product.name}"
                    )
            else:
                # Create new serial number record
                SerialNumber.objects.create(
                    serial_number=product.serial_number,
                    product=product,
                    status="available",
                )
                created_count += 1
                self.stdout.write(f"Created: {product.serial_number} -> {product.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully synced serial numbers. "
                f"Created: {created_count}, Updated: {updated_count}"
            )
        )
