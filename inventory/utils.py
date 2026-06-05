from products.models import Product
from django.db.models import Q

"""
This module contains utility helper functions for the Inventory application.
Supports user access validation and branch-level dataset isolation.
"""

def has_global_inventory_access(user):
    """
    Checks if a user has permission to view inventory across all branches globally.
    Granted to super admins or users with the can_view_all_branches_inventory attribute.
    """
    return getattr(user, "is_super_admin", False) or getattr(
        user, "can_view_all_branches_inventory", False
    )


def get_isolated_products(user):
    """
    Returns a product queryset filtered by user branch associations.
    Users with global access get all products, while branch users are restricted
    to products that have active BranchStock entries at their designated branch.
    """
    qs = Product.objects.all()
    if has_global_inventory_access(user):
        return qs
    if getattr(user, "branch", None):
        return qs.filter(branch_stocks__branch=user.branch).distinct()
    return qs.none()


def filter_by_branch(queryset, user, branch_field="branch"):
    """
    Generic utility that filters any branch-related model queryset by the user's branch.
    If the user has global inventory access, the queryset is returned unaltered.
    """
    if has_global_inventory_access(user):
        return queryset
    if getattr(user, "branch", None):
        return queryset.filter(**{branch_field: user.branch})
    return queryset.none()
