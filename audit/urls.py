from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.AuditLogPageView.as_view(), name="audit-logs"),
]
