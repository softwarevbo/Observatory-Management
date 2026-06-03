from django.urls import path
from . import views

app_name = "bugs"

urlpatterns = [
    path("", views.bug_list, name="bug_list"),
    path("create/", views.bug_create, name="bug_create"),
    path("<int:pk>/", views.bug_detail, name="bug_detail"),
    path("<int:pk>/edit/", views.bug_edit, name="bug_edit"),
    path("<int:pk>/delete/", views.bug_delete, name="bug_delete"),
    path("<int:pk>/comment/", views.bug_comment_add, name="bug_comment_add"),
    path("<int:pk>/resolve/", views.bug_resolve, name="bug_resolve"),
]
