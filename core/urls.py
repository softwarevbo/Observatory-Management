from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("files/", include("files.urls", namespace="files")),
    path("finance/", include("finance.urls", namespace="finance")),
    path("", include("tasks.urls", namespace="tasks")),
    path("chat/", include("chat.urls")),
    # Inventory Routes
    path("inventory/dashboard/", include("dashboard.urls")),
    path("inventory/stock/", include("stock.urls")),
    path("inventory/main/", include("inventory.urls")),
    path("inventory/products/", include("products.urls")),
    path("inventory/audit/", include("audit.urls")),
    path("inventory/reports/", include("reports.urls")),
    path("inventory/procurement/", include("procurement.urls")),
    # Telescope Route
    path("telescope/", include("telescope.urls", namespace="telescope")),
    path("resource-hub/", include("resource_hub.urls", namespace="resource_hub")),
    path("", lambda request: redirect("tasks:dashboard"), name="home"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
