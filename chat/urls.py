from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_home, name='home'),
    path('home/', views.chat_home, name='chat_home'),
    path('project/<str:project_id>/', views.project_chat, name='project_chat'),
    path('api/messages/<str:room_id>/', views.get_messages, name='api_messages'),
    path('create-group/', views.create_group, name='create_group'),
    path('api/search/', views.search_messages, name='search_messages'),
    path('api/upload/', views.upload_chat_file, name='upload_file'),
    path('api/clear/<str:room_id>/', views.clear_chat, name='clear_chat'),
    path('api/quick-chat-list/', views.api_quick_chat_list, name='api_quick_chat_list'),
    path('api/forward/', views.forward_message, name='forward_message'),
    path('api/bulk-delete/', views.bulk_delete_messages, name='bulk_delete_messages'),
    path('api/delete-group/<str:room_id>/', views.delete_group, name='delete_group'),
]
