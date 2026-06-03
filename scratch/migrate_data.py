import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from products.models import Product
from inventory.models import Branch, BranchStock

# Define branches based on Product BRANCH_CHOICES
branches_data = [
    ("koramangala", "IIA, Koramangala"),
    ("hosakote", "IIA, Hosakote (CREST)"),
    ("hanle", "IIA, Hanle (IAO)"),
    ("kavalur", "IIA, Kavalur (VBO)"),
    ("kodaikanal", "IIA, Kodaikanal (KSO)"),
    ("gauribidanur", "IIA, Gauribidanur"),
]

branch_objs = {}
for code, name in branches_data:
    b, _ = Branch.objects.get_or_create(code=code, defaults={"name": name})
    branch_objs[code] = b

products = Product.objects.all()
for p in products:
    if p.branch and p.branch in branch_objs:
        BranchStock.objects.get_or_create(
            branch=branch_objs[p.branch],
            product=p,
            defaults={
                "rack_number": p.rack_number,
                "shelf_number": p.shelf_number,
                # Note: Currently stock limit and quantity are not directly in Product.
                # quantity is calculated dynamically or stored elsewhere? Let's assume defaults for now.
            },
        )

print("Data migration completed.")
