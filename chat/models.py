from django.db import models
from django.conf import settings
import uuid
from .utils import get_avatar_svg
from .encryption_utils import encrypt_data, decrypt_data

"""
This module contains the database models for the Real-time Chat application.
It defines schemas for rooms, encrypted messages, reactions, read receipts, and attachments.
"""

class ChatRoom(models.Model):
    """
    Model representing a distinct chat room or DM thread.
    """
    ROOM_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('project', 'Project Room'),
    ]
    
    # UUID values provide secure, non-guessable identifiers for endpoints
    room_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True, null=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='direct')
    
    # Optional project linkage for automatic scope resolution
    project = models.ForeignKey('tasks.Project', on_delete=models.CASCADE, related_name='chat_rooms', null=True, blank=True)
    room_picture = models.ImageField(upload_to='room_avatars/', null=True, blank=True)
    
    # Participants in the room
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_avatar_url(self, for_user=None):
        """
        Dynamically returns the appropriate avatar image url.
        - For DM rooms, resolves to the other participant's avatar or initials SVG data URI.
        - For group chats, resolves to the group image or None.
        """
        if self.room_type == 'direct' and for_user:
            # Get other user instance in DM
            other = self.participants.exclude(id=for_user.id).first()
            if other and other.profile_picture:
                return other.profile_picture.url
            # Fallback to initials data URI
            return get_avatar_svg(other.username if other else 'User', other.avatar_color if other else '#6366f1')
        if self.room_picture:
            return self.room_picture.url
        return None
    
    def __str__(self):
        return self.name or f"Room {self.room_id}"


class Message(models.Model):
    """
    Model representing an encrypted text, file, voice, or link message sent inside a ChatRoom.
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('voice', 'Voice Note'),
        ('task_link', 'Task Link'),
        ('system', 'System Message'),
    ]
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    
    # The message content is encrypted automatically upon saving using XOR encryption
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    
    # Self-referencing link for message reply structures (threading support)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at'] # Oldest messages display first in logs

    @property
    def decrypted_content(self):
        """Property method that decrypts and returns plain text."""
        return decrypt_data(self.content)

    def save(self, *args, **kwargs):
        """
        Overrides save() to automatically encrypt message text before persisting to database storage.
        """
        if self.content and not self.content.startswith("enc::"):
            self.content = encrypt_data(self.content)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sender}: {self.decrypted_content[:50]}"


class MessageReaction(models.Model):
    """
    Model representing user emoji reactions left on specific messages.
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Enforces that a single user can only react with a specific emoji once per message
        unique_together = ('message', 'user', 'emoji')


class ChatAttachment(models.Model):
    """
    Model representing file attachments uploaded in the chat.
    Encrypts the file name column in the database.
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def decrypted_file_name(self):
        """Property method returning the decrypted file name."""
        return decrypt_data(self.file_name)

    def save(self, *args, **kwargs):
        """Encrypts file name column before saving."""
        if self.file_name and not self.file_name.startswith("enc::"):
            self.file_name = encrypt_data(self.file_name)
        super().save(*args, **kwargs)


class ReadReceipt(models.Model):
    """
    Model representing message read status per participant.
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user')


class UserPresence(models.Model):
    """
    Model tracking user online presence state and last seen timestamp.
    Updated in real time by WebSocket consumers.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presence')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} presence"


class ChatClear(models.Model):
    """
    Model tracking when a user clears their chat room log.
    Messages created before `cleared_at` are filtered out of the user's listing.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    cleared_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'room')
    
    def __str__(self):
        return f"{self.user.username} cleared {self.room}"


# ─── Signals ───
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

@receiver(post_delete, sender=ChatAttachment)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes actual files from disk when a ChatAttachment record is deleted.
    """
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except Exception as e:
            print(f"Error deleting file on signal: {e}")
