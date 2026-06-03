"""this file shows rounting of reports url"""
from django.urls import path
from . import views

urlpatterns = [
    path("statistics/", views.StatisticsReportView.as_view(), name="statistics-report"),
    path(
        "statistics/export/<str:format>/",
        views.statistics_report_export,
        name="statistics-report-export",
    ),
]
