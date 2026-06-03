from django.urls import path

from . import views

urlpatterns = [
    # HTML page routes
    path(
        "superadmin/dashboard/",
        views.SuperAdminDashboardView.as_view(),
        name="superadmin-dashboard",
    ),
    path(
        "superadmin/branches/",
        views.BranchManagementView.as_view(),
        name="inventory-branches",
    ),
    path(
        "branch/dashboard/",
        views.BranchAdminDashboardView.as_view(),
        name="branch-dashboard",
    ),
    path(
        "branch/users/", views.BranchStaffManagementView.as_view(), name="branch-users"
    ),
    path("settings/", views.SystemSettingsView.as_view(), name="system-settings"),
    path(
        "settings/db-backup/",
        views.DatabaseBackupView.as_view(),
        name="inventory_settings",
    ),
    path(
        "users/",
        views.InventoryUserManagementView.as_view(),
        name="inventory-users-management",
    ),
    path(
        "adjustments/",
        views.InventoryAdjustmentPageView.as_view(),
        name="inventory-adjustments-page",
    ),
    path(
        "serials/", views.SerialNumbersPageView.as_view(), name="inventory-serials-page"
    ),
    path(
        "limits/", views.QuantityLimitsPageView.as_view(), name="inventory-limits-page"
    ),
    path("alerts/", views.AlertsPageView.as_view(), name="inventory-alerts-page"),
    path(
        "notifications/",
        views.InventoryNotificationsPageView.as_view(),
        name="inventory-notifications-page",
    ),
    # API routes
    path(
        "api/adjustments/",
        views.InventoryAdjustmentAPI.as_view(),
        name="inventory-adjustments-api",
    ),
    path(
        "api/serials/", views.SerialNumbersAPI.as_view(), name="inventory-serials-api"
    ),
    path("api/limits/", views.QuantityLimitsAPI.as_view(), name="inventory-limits-api"),
    path(
        "api/limits/<int:pk>/",
        views.QuantityLimitDetailAPI.as_view(),
        name="inventory-limit-detail-api",
    ),
    path("api/alerts/", views.AlertsAPI.as_view(), name="inventory-alerts-api"),
    path(
        "api/alerts/<int:pk>/",
        views.AlertDetailAPI.as_view(),
        name="inventory-alert-detail-api",
    ),
    path(
        "alerts/<int:alert_id>/acknowledge/",
        views.AcknowledgeAlertAPI.as_view(),
        name="acknowledge-alert-api",
    ),
    path(
        "alerts/<int:alert_id>/resolve/",
        views.ResolveAlertAPI.as_view(),
        name="resolve-alert-api",
    ),
    path("rentals/", views.RentalManagementView.as_view(), name="rental-management"),
]

urlpatterns += [
    path("limits/standard/", views.set_standard_limit, name="set-standard-limit"),
    path("shortage/", views.inventory_shortage_view, name="inventory-shortage-page"),
    path(
        "shortage/export/csv/",
        views.inventory_shortage_export_csv,
        name="inventory-shortage-export-csv",
    ),
    path(
        "shortage/export/pdf/",
        views.inventory_shortage_export_pdf,
        name="inventory-shortage-export-pdf",
    ),
]
