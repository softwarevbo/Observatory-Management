from django.urls import path

from . import views

"""
This module registers URL routing mappings for the Files app actions.
Matches user actions to lists controllers, upload operations, serving views, and movements APIs.
"""

app_name = "files"

urlpatterns = [
    # Main listing view
    path("", views.file_list, name="file_list"),
    
    # Upload views
    path("upload/", views.file_upload, name="file_upload"),
    
    # Detail and serving endpoints
    path("<int:pk>/", views.file_detail, name="file_detail"),
    path("<int:pk>/download/", views.file_download, name="file_download"),
    path("<int:pk>/view/", views.file_view, name="file_view"),
    
    # Management and Edit actions
    path("<int:pk>/edit/", views.file_edit, name="file_edit"),
    path("<int:pk>/content-edit/", views.file_content_edit, name="file_content_edit"),
    path("<int:pk>/delete/", views.file_delete, name="file_delete"),
    
    # Trash operations (restore, permanent delete, visibility adjustments)
    path("<int:pk>/restore/", views.file_restore, name="file_restore"),
    path("<int:pk>/permanent-delete/", views.file_permanent_delete, name="file_permanent_delete"),
    path("<int:pk>/hide-from-trash/", views.file_hide_from_trash, name="file_hide_from_trash"),
    
    # Access rights overrides
    path("<int:pk>/access/", views.file_access, name="file_access"),
    
    # Project specific file listings
    path("project/<int:pk>/", views.project_files, name="project_files"),
    
    # Categories / Directory nodes controls
    path("project/<int:pk>/categories/new/", views.category_create, name="category_create"),
    path("api/project-categories/", views.project_categories_api, name="project_categories_api"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/download/", views.download_folder, name="download_folder"),
    
    # Movements, portal views, and audits
    path("settings/", views.system_settings, name="system_settings"),
    path("move-item/", views.move_item, name="move_item"),
    path("manage-resource/", views.manage_resource, name="manage_resource"),
    path("audit-logs/", views.file_audit_logs, name="file_audit_logs"),
    path("bulk-action/", views.bulk_file_action, name="bulk_file_action"),
]
