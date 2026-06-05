from inventory.models import InventoryNotification, InventoryUser
from django.db.models import Q

"""
This module contains notification dispatch helpers for the Inventory application.
Sends notifications to all active admin and super admin users.
"""

def notify_inventory_admins(sender, notification_type, title, message, target_url=None):
    """
    Sends an internal notification to all active administrative inventory users.
    Filters users that are super admins, branch admins, or have administrative roles.
    """
    admin_users = InventoryUser.objects.filter(
        Q(role="admin") | Q(role="super_admin") | Q(role="branch_admin"),
        is_active=True
    )
    sender_obj = sender if isinstance(sender, InventoryUser) else None
    for admin_user in admin_users:
        InventoryNotification.objects.create(
            recipient=admin_user,
            sender=sender_obj,
            notification_type=notification_type,
            title=title,
            message=message,
            target_url=target_url or "",
        )
