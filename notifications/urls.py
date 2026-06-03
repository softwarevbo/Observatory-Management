from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notifications_list, name="notifications"),
    path("<int:pk>/read/", views.notification_read, name="notification_read"),
]
