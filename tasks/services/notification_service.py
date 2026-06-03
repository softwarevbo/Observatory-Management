from notifications.models import Notification


class NotificationService:
    @staticmethod
    def create_notification(
        recipient,
        sender,
        notification_type,
        title,
        message,
        task=None,
        project=None,
        test_case=None,
    ):
        """
        Creates a notification for a user.
        """
        if recipient and recipient != sender:
            notif = Notification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type=notification_type,
                title=title,
                message=message,
                task=task,
                project=project,
                test_case=test_case,
            )
            # Send dynamic notification update via Channels
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                if channel_layer:
                    unread_count = Notification.objects.filter(recipient=recipient, is_read=False).count()
                    async_to_sync(channel_layer.group_send)(
                        f"user_{recipient.id}",
                        {
                            "type": "new_notification",
                            "unread_count": unread_count,
                            "notification": {
                                "id": notif.id,
                                "title": notif.title,
                                "message": notif.message,
                                "notification_type": notif.notification_type,
                            }
                        }
                    )
            except Exception as e:
                print(f"Error sending live notification websocket event: {e}")
            return notif
        return None

    @staticmethod
    def mark_as_read(notification_id, user):
        """Marks a notification as read."""
        from django.shortcuts import get_object_or_404

        notification = get_object_or_404(
            Notification, id=notification_id, recipient=user
        )
        notification.is_read = True
        notification.save()
        return notification
