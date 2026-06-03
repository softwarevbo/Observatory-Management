from django.urls import path

from . import views

urlpatterns = [
    # HTML page routes
    path("", views.DashboardPageView.as_view(), name="dashboard-page"),
    path("overview/", views.DashboardOverview.as_view(), name="dashboard-overview"),
    # API routes (for programmatic access)
    path("api/", views.DashboardOverview.as_view(), name="dashboard-api"),
]
