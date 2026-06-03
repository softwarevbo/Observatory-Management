from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.ProcurementUploadView.as_view(), name="procurement-upload"),
    path(
        "restock/", views.ProcurementRestockView.as_view(), name="procurement-restock"
    ),
    path("send-all-alerts/", views.send_all_alerts, name="send-all-alerts"),
    path(
        "template/",
        views.DownloadProcurementTemplateView.as_view(),
        name="download-procurement-template",
    ),
]
