from django.urls import path

from . import views

"""
This module defines URL routing configurations for the accounts application.
It uses standard Django path mapping to route incoming HTTP requests to their matching view logic.

The routes are organized into four logical segments:
1. Authentication (Login, Logout views across various portals)
2. Custom User Management actions (Creating, editing, deleting, role updating for PM users)
3. Specialized User Management for sub-apps (Inventory and Telescope users)
4. Self-service profile, settings, and password updates
"""

# Namespace name for routing reverse lookups (e.g. reverse("accounts:login"))
app_name = "accounts"

urlpatterns = [
    # ─── Authentication Routes ──────────────────────────────────────────────────
    # Default system login page
    path("login/", views.login_view, name="login"),
    
    # Specific login views routing for inventory staff and telescope operators
    path("inventory_login/", views.inventory_login, name="inventory_login"),
    path("telescope_login/", views.telescope_login, name="telescope_login"),
    
    # Global logout route
    path("logout/", views.logout_view, name="logout"),
    
    # ─── User Management (Admin only) ──────────────────────────────────────────
    # Lists users depending on tab settings (Project Management, Inventory, Telescope)
    path("users/", views.user_list, name="user_list"),
    
    # Create a new PM user
    path("users/create/", views.user_create, name="user_create"),
    
    # View details of a specific user profile
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    
    # Edit details of a specific user
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    
    # Admin tool to override/reset a user's password
    path(
        "users/<int:pk>/reset-password/",
        views.user_reset_password,
        name="user_reset_password",
    ),
    
    # Delete a user account (destructive confirmation action)
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    
    # Toggle user active status (Active/Inactive toggle)
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle"),
    
    # API endpoint to change user's role via POST requests
    path(
        "users/<int:pk>/change-role/", views.change_user_role, name="user_change_role"
    ),
    
    # ─── Inventory User Management (Admin only) ─────────────────────────────────
    # CRUD endpoints for managing separate InventoryUser accounts
    path("users/inventory/create/", views.inventory_user_create, name="inventory_user_create"),
    path("users/inventory/<int:pk>/edit/", views.inventory_user_edit, name="inventory_user_edit"),
    path("users/inventory/<int:pk>/delete/", views.inventory_user_delete, name="inventory_user_delete"),
    path("users/inventory/<int:pk>/toggle/", views.inventory_user_toggle, name="inventory_user_toggle"),
    
    # ─── Telescope User Management (Admin only) ─────────────────────────────────
    # CRUD endpoints for managing Telescope operators/permissions
    path("users/telescope/create/", views.telescope_user_create, name="telescope_user_create"),
    path("users/telescope/<int:pk>/edit/", views.telescope_user_edit, name="telescope_user_edit"),
    path("users/telescope/<int:pk>/delete/", views.telescope_user_delete, name="telescope_user_delete"),
    path("users/telescope/<int:pk>/toggle/", views.telescope_user_toggle, name="telescope_user_toggle"),
    
    # ─── Profile & Self-Service Settings ───────────────────────────────────────
    # Profile viewing dashboard (Self)
    path("profile/", views.profile_view, name="profile"),
    
    # Password changing form (Self)
    path("change-password/", views.change_password, name="change_password"),
    
    # General app theme preferences, notifications toggle, issue reporting configurations (Self)
    path("settings/", views.settings_view, name="settings"),
    
    # Specialized profile pages and settings for sub-app portals
    path("inventory/profile/", views.inventory_profile_view, name="inventory_profile"),
    path("inventory/settings/", views.inventory_settings_view, name="inventory_settings"),
    path("telescope/profile/", views.telescope_profile_view, name="telescope_profile"),
    path("telescope/settings/", views.telescope_settings_view, name="telescope_settings"),
]
