from django.urls import path
from . import views

"""
This module defines URL routing configurations for the chat application.
"""

app_name = 'chat'

urlpatterns = [
    # Main Chat room screen
    path('', views.chat_home, name='home'),
    path('home/', views.chat_home, name='chat_home'),
    
    # Project specific workspace room
    path('project/<str:project_id>/', views.project_chat, name='project_chat'),
    
    # REST API endpoints for JavaScript AJAX requests
    # Fetches recent message dataset for a specific room
    path('api/messages/<str:room_id>/', views.get_messages, name='api_messages'),
    
    # Creates a group chat room
    path('create-group/', views.create_group, name='create_group'),
    
    # Searches decrypted message text
    path('api/search/', views.search_messages, name='search_messages'),
    
    # Handles file/attachment uploads inside chats
    path('api/upload/', views.upload_chat_file, name='upload_file'),
    
    # Clears chat history for the user (sets hidden boundaries)
    path('api/clear/<str:room_id>/', views.clear_chat, name='clear_chat'),
    
    # Dynamic JSON list payload containing recent chats, users, unread stats, and attachments
    path('api/quick-chat-list/', views.api_quick_chat_list, name='api_quick_chat_list'),
    
    # Forwards a message to another room
    path('api/forward/', views.forward_message, name='forward_message'),
    
    # Performs bulk deletion of messages
    path('api/bulk-delete/', views.bulk_delete_messages, name='bulk_delete_messages'),
    
    # Deletes a group chat room (owner only)
    path('api/delete-group/<str:room_id>/', views.delete_group, name='delete_group'),
    
    # Leaves a group chat room
    path('api/leave-group/<str:room_id>/', views.leave_group, name='leave_group'),
    
    # Removes a member from group chat room (owner only)
    path('api/remove-member/<str:room_id>/<int:user_id>/', views.remove_member, name='remove_member'),

    # Returns users not yet in a group (for admin Add Member picker)
    path('api/non-members/<str:room_id>/', views.get_non_members, name='non_members'),

    # Adds a user to a group chat room (admin only)
    path('api/add-member/<str:room_id>/<int:user_id>/', views.add_member, name='add_member'),
]
