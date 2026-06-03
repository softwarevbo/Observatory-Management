from django.db import models
from django.conf import settings
import uuid

class ChatRoom(models.Model):
    ROOM_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('project', 'Project Room'),
    ]
    
    room_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True, null=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='direct')
    project = models.ForeignKey('tasks.Project', on_delete=models.CASCADE, related_name='chat_rooms', null=True, blank=True)
    room_picture = models.ImageField(upload_to='room_avatars/', null=True, blank=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_avatar_url(self, for_user=None):
        if self.room_type == 'direct' and for_user:
            other = self.participants.exclude(id=for_user.id).first()
            if other and other.profile_picture:
                return other.profile_picture.url
            return f"https://ui-avatars.com/api/?name={other.username if other else 'User'}&background=random&size=40&bold=true"
        if self.room_picture:
            return self.room_picture.url
        return None
    
    def __str__(self):
        return self.name or f"Room {self.room_id}"

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('voice', 'Voice Note'),
        ('task_link', 'Task Link'),
        ('system', 'System Message'),
    ]
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"

class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user', 'emoji')

class ChatAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class ReadReceipt(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user')

class UserPresence(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presence')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    
class ChatClear(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    cleared_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'room')
    
    def __str__(self):
        return f"{self.user.username} cleared {self.room}"

from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

@receiver(post_delete, sender=ChatAttachment)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except Exception as e:
            print(f"Error deleting file on signal: {e}")
