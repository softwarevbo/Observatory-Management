from inventory.models import InventoryNotification, InventoryUser


def notify_inventory_admins(sender, notification_type, title, message, target_url=None):
    admin_users = InventoryUser.objects.filter(role="admin", is_active=True)
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
