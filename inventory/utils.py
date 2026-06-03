from products.models import Product
from django.db.models import Q


def has_global_inventory_access(user):
    """Check if user has global inventory access."""
    return getattr(user, "is_super_admin", False) or getattr(
        user, "can_view_all_branches_inventory", False
    )


def get_isolated_products(user):
    """Get products the user is allowed to see based on branch isolation."""
    qs = Product.objects.all()
    if has_global_inventory_access(user):
        return qs
    if getattr(user, "branch", None):
        return qs.filter(branch_stocks__branch=user.branch).distinct()
    return qs.none()


def filter_by_branch(queryset, user, branch_field="branch"):
    """Generic filter for models that have a branch field."""
    if has_global_inventory_access(user):
        return queryset
    if getattr(user, "branch", None):
        return queryset.filter(**{branch_field: user.branch})
    return queryset.none()
