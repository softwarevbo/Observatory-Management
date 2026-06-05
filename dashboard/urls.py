from django.urls import path
from . import views

"""
This module defines URL routing configurations for the Inventory Dashboard overview.
"""

urlpatterns = [
    # Main Dashboard Page (branch isolated)
    path("", views.DashboardPageView.as_view(), name="dashboard-page"),
    
    # Static mockup dashboard overview route
    path("overview/", views.DashboardOverview.as_view(), name="dashboard-overview"),
    
    # API endpoints representing dashboard values in JSON format
    path("api/", views.DashboardOverview.as_view(), name="dashboard-api"),
]
