from django.urls import path
from . import views

"""
This module defines URL routing configurations for the Bug Tracking application.
"""

app_name = "bugs"

urlpatterns = [
    # Main bug listing page (filterable)
    path("", views.bug_list, name="bug_list"),
    
    # Create new bug report
    path("create/", views.bug_create, name="bug_create"),
    
    # Detail view of a bug report
    path("<int:pk>/", views.bug_detail, name="bug_detail"),
    
    # Edit/update bug details
    path("<int:pk>/edit/", views.bug_edit, name="bug_edit"),
    
    # Soft delete a bug report (moves to trash)
    path("<int:pk>/delete/", views.bug_delete, name="bug_delete"),
    
    # Add comment/reply to bug report
    path("<int:pk>/comment/", views.bug_comment_add, name="bug_comment_add"),
    
    # Log developer resolution details and update bug status
    path("<int:pk>/resolve/", views.bug_resolve, name="bug_resolve"),
]
