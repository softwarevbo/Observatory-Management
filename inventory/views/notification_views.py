from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from ..models import InventoryNotification

"""
This module processes internal alerts/notifications lists and read status settings.
"""


class InventoryNotificationsPageView(View):
    """
    View class rendering historical log alerts targeted to the logged-in user.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        notifications = InventoryNotification.objects.filter(recipient=request.user)
        status_filter = request.GET.get("status", "")
        type_filter = request.GET.get("type", "")
        date_filter = request.GET.get("date", "")
        search = request.GET.get("search", "")

        # Apply filtering parameters
        if status_filter == "unread":
            notifications = notifications.filter(is_read=False)
        elif status_filter == "read":
            notifications = notifications.filter(is_read=True)
        if type_filter:
            notifications = notifications.filter(notification_type=type_filter)
        if date_filter:
            notifications = notifications.filter(created_at__date=date_filter)
        if search:
            notifications = notifications.filter(
                Q(title__icontains=search) | Q(message__icontains=search)
            )

        paginator = Paginator(notifications, 30)
        page_number = request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        return render(
            request,
            "inventory/notifications.html",
            {
                "notifications": page_obj.object_list,
                "page_obj": page_obj,
                "status_filter": status_filter,
                "type_filter": type_filter,
                "date_filter": date_filter,
                "search": search,
                "type_choices": InventoryNotification.NOTIFICATION_TYPE_CHOICES,
            },
        )

    def post(self, request):
        """
        Marks single notifications as read or batch clears all active notices.
        """
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        notification_id = request.POST.get("notification_id")
        action = request.POST.get("action")
        if action == "mark_all_read":
            InventoryNotification.objects.filter(
                recipient=request.user, is_read=False
            ).update(is_read=True)
            messages.success(request, "All notifications marked as read.")
        elif notification_id:
            notification = get_object_or_404(
                InventoryNotification, id=notification_id, recipient=request.user
            )
            notification.is_read = True
            notification.save(update_fields=["is_read"])
            messages.success(request, "Notification marked as read.")
        return redirect("inventory-notifications-page")
