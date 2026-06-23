from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path
from django.views.generic.base import RedirectView
from . import views

"""
This module defines the global URL routing configurations for the IIA Management system.
It aggregates routing maps from all application modules (accounts, finance, tasks, stock, etc.).
"""

urlpatterns = [
    # Favicon redirection
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.png")),
    
    # 404 test page
    path("404/", lambda request: render(request, "404.html"), name="test-404"),
    
    # Django Admin site
    path("admin/", admin.site.urls),
    
    # Modular application routes
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("files/", include("files.urls", namespace="files")),
    path("finance/", include("finance.urls", namespace="finance")),
    path("", include("tasks.urls", namespace="tasks")),
    path("chat/", include("chat.urls")),
    
    # Inventory Isolated Apps Routes
    path("inventory/dashboard/", include("dashboard.urls")),
    path("inventory/stock/", include("stock.urls")),
    path("inventory/main/", include("inventory.urls")),
    path("inventory/products/", include("products.urls")),
    path("inventory/audit/", include("audit.urls")),
    path("inventory/reports/", include("reports.urls")),
    path("inventory/procurement/", include("procurement.urls")),
    
    # Telescope and general Observatory workspaces
    path("telescope/", include("telescope.urls", namespace="telescope")),
    path("resource-hub/", include("resource_hub.urls", namespace="resource_hub")),
    
    # Root dashboard default redirection
    path("", views.home_redirect_view, name="home"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 handler registration
handler404 = 'core.views.custom_page_not_found_view'

# ─── PRODUCTION/NON-DEBUG STATIC SERVING ───
# If DEBUG is False and collectstatic hasn't run, serve static files using static fallback server.
if not settings.DEBUG:
    import os
    from django.views.static import serve
    from django.urls import re_path

    static_dir = settings.STATIC_ROOT
    if not os.path.exists(static_dir) or not os.listdir(static_dir):
        static_dir = settings.STATICFILES_DIRS[0]

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': static_dir}),
    ]

# ─── DJANGO DEBUG TOOLBAR ───
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
