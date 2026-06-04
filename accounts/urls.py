from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Auth
    path("login/", views.login_view, name="login"),
    path("inventory_login/", views.inventory_login, name="inventory_login"),
    path("telescope_login/", views.telescope_login, name="telescope_login"),
    path("logout/", views.logout_view, name="logout"),
    # User Management (Admin only)
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path(
        "users/<int:pk>/reset-password/",
        views.user_reset_password,
        name="user_reset_password",
    ),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle"),
    path(
        "users/<int:pk>/change-role/", views.change_user_role, name="user_change_role"
    ),
    # Inventory User Management (Admin only)
    path("users/inventory/create/", views.inventory_user_create, name="inventory_user_create"),
    path("users/inventory/<int:pk>/edit/", views.inventory_user_edit, name="inventory_user_edit"),
    path("users/inventory/<int:pk>/delete/", views.inventory_user_delete, name="inventory_user_delete"),
    path("users/inventory/<int:pk>/toggle/", views.inventory_user_toggle, name="inventory_user_toggle"),
    # Telescope User Management (Admin only)
    path("users/telescope/create/", views.telescope_user_create, name="telescope_user_create"),
    path("users/telescope/<int:pk>/edit/", views.telescope_user_edit, name="telescope_user_edit"),
    path("users/telescope/<int:pk>/delete/", views.telescope_user_delete, name="telescope_user_delete"),
    path("users/telescope/<int:pk>/toggle/", views.telescope_user_toggle, name="telescope_user_toggle"),
    # Profile (self)
    path("profile/", views.profile_view, name="profile"),
    path("change-password/", views.change_password, name="change_password"),
    path("settings/", views.settings_view, name="settings"),
    # Inventory Profile & Settings
    path("inventory/profile/", views.inventory_profile_view, name="inventory_profile"),
    path("inventory/settings/", views.inventory_settings_view, name="inventory_settings"),
    # Telescope Profile & Settings
    path("telescope/profile/", views.telescope_profile_view, name="telescope_profile"),
    path("telescope/settings/", views.telescope_settings_view, name="telescope_settings"),
]
