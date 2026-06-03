from django.urls import path
from . import views

app_name = "telescope"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("<int:pk>/", views.telescope_detail, name="detail"),
    path("create/", views.telescope_create, name="create"),
    path("<int:pk>/edit/", views.telescope_edit, name="edit"),
    path("<int:pk>/delete/", views.telescope_delete, name="delete"),
]
