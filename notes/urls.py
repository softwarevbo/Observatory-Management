from django.urls import path
from . import views

"""
This module registers URL routing configurations for the Notes application.
Note: These views are integrated inside the tasks: namespace in tasks/urls.py.
"""

app_name = "notes"

urlpatterns = [
    path("", views.kb_overview, name="kb_overview"),
    path("new/", views.kb_create_global, name="kb_create_global"),
    path("project/<int:pk>/", views.kb_list, name="kb_list"),
    path("project/<int:pk>/new/", views.kb_create, name="kb_create"),
    path("<int:pk>/", views.kb_detail, name="kb_detail"),
    path("<int:pk>/edit/", views.kb_edit, name="kb_edit"),
    path("<int:pk>/access/", views.kb_access, name="kb_access"),
    path("<int:pk>/delete/", views.kb_delete, name="kb_delete"),
    path("<int:pk>/restore/", views.note_restore, name="note_restore"),
    path("<int:pk>/permanent-delete/", views.note_permanent_delete, name="note_permanent_delete"),
]
