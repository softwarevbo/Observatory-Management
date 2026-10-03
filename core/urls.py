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
    path("chat/", include("chat.urls")),

    # Project Management Primary Workspace (/projectmanagement/...)
    path("projectmanagement/", include("tasks.urls", namespace="tasks")),
    path("dashboard/", lambda request: redirect("/projectmanagement/dashboard/")),
    path("projects/", lambda request: redirect("/projectmanagement/projects/")),
    path("tasks/", lambda request: redirect("/projectmanagement/tasks/")),

    # Inventory Management Primary Workspace (/inventorymanagement/...)
    path("inventorymanagement/", include("inventory.urls")),
    path("inventorymanagement/dashboard/", include("dashboard.urls")),
    path("inventorymanagement/stock/", include("stock.urls")),
    path("inventorymanagement/main/", include("inventory.urls")),
    path("inventorymanagement/products/", include("products.urls")),
    path("inventorymanagement/audit/", include("audit.urls")),
    path("inventorymanagement/reports/", include("reports.urls")),
    path("inventorymanagement/procurement/", include("procurement.urls")),
    path("inventory/dashboard/", lambda request: redirect("/inventorymanagement/dashboard/")),
    path("inventory/stock/", lambda request: redirect("/inventorymanagement/stock/")),
    path("inventory/main/", lambda request: redirect("/inventorymanagement/main/")),

    # Telescope Control Primary Workspace (/telescopecontrol/...)
    path("telescopecontrol/", include("telescope.urls", namespace="telescope")),
    path("telescope/", lambda request: redirect("/telescopecontrol/")),

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

# # ─── DJANGO DEBUG TOOLBAR ───
# if settings.DEBUG:
#     import debug_toolbar
# 
#     urlpatterns += [
#         path("__debug__/", include(debug_toolbar.urls)),
#     ]
