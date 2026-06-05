from django.urls import path

from . import views

"""
This module defines URL routing configurations for the audit logging application.
Maps the request path pattern directly to the Class-Based View: `AuditLogPageView`.
"""

urlpatterns = [
    # Maps 'logs/' requests to the class-based AuditLogPageView.
    # .as_view() initializes the class wrapper to handle HTTP requests (GET, POST).
    path("logs/", views.AuditLogPageView.as_view(), name="audit-logs"),
]
