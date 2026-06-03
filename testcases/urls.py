from django.urls import path
from . import views

app_name = "testcases"

urlpatterns = [
    path("project/<int:project_id>/bulk-create/", views.test_case_bulk_create, name="test_case_bulk_create"),
    path("project/<int:project_id>/create/", views.test_case_create, name="test_case_create"),
    path("<int:pk>/", views.test_case_detail, name="test_case_detail"),
    path("<int:pk>/edit/", views.test_case_edit, name="test_case_edit"),
    path("<int:pk>/delete/", views.test_case_delete, name="test_case_delete"),
    path("<int:pk>/verify/", views.test_case_verify, name="test_case_verify"),
    path("<int:pk>/comment/add/", views.test_case_comment_add, name="test_case_comment_add"),
]
