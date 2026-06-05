from inventory.models import InventoryNotification, InventoryUser

"""
This module contains context processors for the Inventory application.
Context processors expose variables globally to all templates.
"""

def inventory_notifications_count(request):
    """
    Exposes the count of unread inventory notifications for the currently logged-in InventoryUser.
    """
    if request.user.is_authenticated and isinstance(request.user, InventoryUser):
        unread = InventoryNotification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return {"unread_inventory_count": unread}
    return {}
