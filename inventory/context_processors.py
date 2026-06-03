from inventory.models import InventoryNotification, InventoryUser


def inventory_notifications_count(request):
    if request.user.is_authenticated and isinstance(request.user, InventoryUser):
        unread = InventoryNotification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return {"unread_inventory_count": unread}
    return {}
