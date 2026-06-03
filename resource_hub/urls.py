from django.urls import path
from . import views

app_name = 'resource_hub'

urlpatterns = [
    # Main Dashboard Listing & creation
    path('', views.repo_list, name='repo_list'),
    path('new/', views.repo_create, name='repo_create'),
    path('invitation/<int:invite_id>/accept/', views.repo_accept_invite, name='repo_accept_invite'),
    path('invitation/<int:invite_id>/decline/', views.repo_decline_invite, name='repo_decline_invite'),

    # Smart HTTP Git backend
    path('git/<slug:slug>.git/<path:git_path>', views.git_smart_http_view, name='git_smart_http'),

    # Specific Web actions (must come before general slug views to avoid matching conflicts)
    path('<slug:slug>/commits/', views.repo_commits, name='repo_commits'),
    path('<slug:slug>/commit/<str:commit_hash>/', views.repo_commit_detail, name='repo_commit_detail'),
    path('<slug:slug>/upload/', views.repo_upload, name='repo_upload'),
    path('<slug:slug>/settings/', views.repo_settings, name='repo_settings'),
    path('<slug:slug>/guide/', views.repo_user_guide, name='repo_user_guide'),
    path('<slug:slug>/logs/', views.repo_logs, name='repo_logs'),
    path('<slug:slug>/archive/<str:ref>/zip/', views.repo_download_zip, name='repo_download_zip'),
    path('<slug:slug>/new-file/', views.repo_create_file, name='repo_create_file'),
    path('<slug:slug>/blob/<str:ref>/<path:path>', views.repo_file_view, name='repo_file_view'),
    path('<slug:slug>/raw/<str:ref>/<path:path>', views.repo_raw_view, name='repo_raw_view'),

    # Directory and code browser
    path('<slug:slug>/', views.repo_code, name='repo_code'),
    path('<slug:slug>/tree/<path:path>', views.repo_code, name='repo_code_dir'),
]
