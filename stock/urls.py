from django.urls import path
from . import views

urlpatterns = [
    path("in/", views.StockInPageView.as_view(), name="stock-in-page"),
    path("out/", views.StockOutPageView.as_view(), name="stock-out-page"),
    path(
        "transfer/", views.StockTransferPageView.as_view(), name="stock-transfer-page"
    ),
    path(
        "transfer/<int:pk>/receive/",
        views.StockTransferReceiveView.as_view(),
        name="stock-transfer-receive",
    ),
    path("api/in/", views.StockIn.as_view(), name="stock-in-api"),
    path("api/out/", views.StockOut.as_view(), name="stock-out-api"),
    path(
        "template/in/",
        views.DownloadBulkStockInTemplate.as_view(),
        name="download-stock-in-template",
    ),
    path(
        "template/out/",
        views.DownloadBulkStockOutTemplate.as_view(),
        name="download-stock-out-template",
    ),
]
