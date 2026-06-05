from django.urls import path
from . import views

"""
This module registers URL routing configurations for the Notifications application.
Note: These views are integrated inside the tasks: namespace in tasks/urls.py.
"""

app_name = "notifications"

urlpatterns = [
    path("", views.notifications_list, name="notifications"),
    path("<int:pk>/read/", views.notification_read, name="notification_read"),
]
