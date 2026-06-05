import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message, UserPresence
from django.utils import timezone
from accounts.models import User

"""
This module defines ASGI consumers for managing real-time WebSocket communication.
It handles live chat events (sending, editing, deleting messages, reactions, read receipts,
typing states) and global online user presence changes.

Important design patterns used here:
1. `AsyncWebsocketConsumer`: Handles WebSocket requests asynchronously to maximize performance.
2. `database_sync_to_async`: Wraps Django ORM database queries in synchronous threads so they do
   not block the main asynchronous event loop.
3. `channel_layer.group_send`: Dynamic broadcasts to multiple socket users connected in a room group.
"""

class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer handling real-time messaging, status updates, reactions, and room groups events.
    """
    
    @database_sync_to_async
    def get_room_group_name_async(self, room):
        """Resolves standard Channel group name string using room UUID."""
        return f"chat_{room.room_id}"

    async def connect(self):
        """
        Invoked when a user initiates a WebSocket connection hand-shake.
        Resolves room IDs, manages DM creation/access, registers the channel to room groups,
        updates presence status, and marks messages as read.
        """
        self.user = self.scope["user"]
        
        # Security Guard: Only authenticated user sessions are permitted to establish sockets
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_name = self.scope['url_route']['kwargs']['room_id']
        print(f"[ChatConsumer] Connecting to room: {self.room_name} for user: {self.user.username}")
        
        try:
            # ─── DM ROOM RESOLUTION ───
            # Direct Messages are identified by paths starting with 'DM-'
            if self.room_name.startswith('DM-'):
                participant_id = self.room_name.split('-')[1]
                # Standardize room name so that 'DM-1-2' and 'DM-2-1' result in the same name
                normalized_name = f"DM-{min(str(self.user.id), str(participant_id))}-{max(str(self.user.id), str(participant_id))}"

                # Query database to find if DM room already exists, fallback to creating it
                existing = await database_sync_to_async(
                    ChatRoom.objects.filter(name=normalized_name).order_by('pk').first
                )()
                if existing:
                    self.room = existing
                else:
                    self.room, _ = await database_sync_to_async(
                        ChatRoom.objects.get_or_create
                    )(name=normalized_name, defaults={'room_type': 'direct'})

                # Add current user to room participants listing
                await database_sync_to_async(self.room.participants.add)(self.user)
                # Add recipient to room participants listing
                try:
                    other_user = await database_sync_to_async(User.objects.get)(id=participant_id)
                    await database_sync_to_async(self.room.participants.add)(other_user)
                except Exception as e:
                    print(f"[ChatConsumer] Error adding other participant: {e}")
            
            # ─── STANDARD ROOM RESOLUTION ───
            else:
                try:
                    self.room = await database_sync_to_async(ChatRoom.objects.get)(room_id=self.room_name)
                except Exception as e:
                    print(f"[ChatConsumer] Room not found: {self.room_name} - {e}")
                    await self.close()
                    return

            # Consistently resolve the group channel name
            self.room_group_name = await self.get_room_group_name_async(self.room)
        except Exception as e:
            print(f"[ChatConsumer] Connection error: {e}")
            await self.close()
            return
            
        # Register channel to standard room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept the WebSocket hand-shake request
        await self.accept()
        
        # Register channel to global presence notification group
        await self.channel_layer.group_add("presence", self.channel_name)
        await self.update_user_presence(True) # Mark user online in database
        
        # Broadcast presence change to other users
        await self.channel_layer.group_send("presence", {
            "type": "presence_change",
            "user_id": self.user.id,
            "status": "online"
        })

        # Mark all unread messages in the room as read, and broadcast status to participants
        await self.mark_messages_as_read()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'messages_read',
                'user': self.user.username,
                'reader_id': self.user.id
            }
        )

    async def disconnect(self, close_code):
        """
        Invoked when WebSocket connection terminates.
        Cleans up group channel registrations and updates user presence state.
        """
        # Guard: if connect() failed before setting room_group_name, skip room ops
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        # Update presence status to offline
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.update_user_presence(False)
            await self.channel_layer.group_send("presence", {
                "type": "presence_change",
                "user_id": self.user.id,
                "status": "offline"
            })
        await self.channel_layer.group_discard("presence", self.channel_name)

    async def receive(self, text_data):
        """
        Invoked when socket client sends data frame package to the server.
        Parses action types and delegates execution.
        """
        data = json.loads(text_data)
        message_type = data.get('type')
        
        # ─── ACTION: New Message ───
        if message_type == 'chat_message':
            content = data.get('message')
            parent_id = data.get('parent_id')
            msg_type = data.get('message_type', 'text')
            file_url = data.get('file_url')
            file_name = data.get('file_name')
            file_type = data.get('file_type')
            
            # Save message to database asynchronously
            msg_data = await self.save_message(content, parent_id, msg_type)
            
            # Send message data to room group channel layer
            broadcast_data = {
                'type': 'chat_message',
                'id': msg_data['id'],
                'message': content,
                'sender': self.user.username,
                'sender_avatar': self.user.profile_picture.url if self.user.profile_picture else None,
                'timestamp': msg_data['created_at'].strftime('%H:%M'),
                'raw_timestamp': msg_data['created_at'].isoformat(),
                'message_type': msg_type,
                'file_url': file_url,
                'file_name': file_name,
                'file_type': file_type,
                'room_id': str(self.room.room_id)
            }
            
            # Handle reply references in broadcast payload
            if msg_data['parent_sender']:
                broadcast_data['parent_content'] = msg_data['parent_content']
                broadcast_data['parent_sender'] = msg_data['parent_sender']
                broadcast_data['parent_id'] = msg_data['parent_id']
                
            await self.channel_layer.group_send(
                self.room_group_name,
                broadcast_data
            )

            # Send private message alert notifications to other participants
            try:
                participants = await self.get_room_participants()
                for p in participants:
                    if p.id != self.user.id:
                        unread_count = await self.get_participant_room_unread(p)
                        await self.channel_layer.group_send(
                            f"user_{p.id}",
                            {
                                "type": "chat_notification",
                                "room_id": str(self.room.room_id),
                                "sender": self.user.username,
                                "content": content if msg_type == 'text' else 'File',
                                "unread_count": unread_count
                            }
                        )
            except Exception as e:
                print(f"Error sending chat notification: {e}")
        
        # ─── ACTION: Read Receipt ───
        elif message_type == 'read_receipt':
            await self.mark_messages_as_read()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'user': self.user.username,
                    'reader_id': self.user.id
                }
            )

        # ─── ACTION: Edit Message ───
        elif message_type == 'edit_message':
            message_id = data.get('message_id')
            content = data.get('message')
            await self.update_message(message_id, content)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'message': content
                }
            )

        # ─── ACTION: Delete Message ───
        elif message_type == 'delete_message':
            message_id = data.get('message_id')
            await self.delete_message(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id
                }
            )

        # ─── ACTION: Add Reaction ───
        elif message_type == 'add_reaction':
            message_id = data.get('message_id')
            emoji = data.get('emoji')
            await self.save_reaction(message_id, emoji)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reaction',
                    'message_id': message_id,
                    'emoji': emoji,
                    'user': self.user.username
                }
            )
        
        # ─── ACTION: User Typing ───
        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'user': self.user.username,
                    'is_typing': data.get('is_typing')
                }
            )

    # ─── WebSocket Event Handlers ───
    # These methods are triggered by group broadcasts and forward payloads to active clients.

    async def presence_change(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence_change',
            'user_id': event['user_id'],
            'status': event['status']
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def messages_read(self, event):
        await self.send(text_data=json.dumps(event))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps(event))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps(event))

    async def message_reaction(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user'],
            'is_typing': event['is_typing']
        }))

    # ─── Database Sync Wrappers ───
    # Queries executing Django ORM calls wrapped in asynchronous execution threads.

    @database_sync_to_async
    def save_message(self, content, parent_id=None, message_type='text'):
        """Asynchronously saves message records to the database."""
        room = self.room
        
        # Resolve parent message object if it's a thread reply
        parent = None
        if parent_id:
            try:
                parent = Message.objects.select_related('sender').get(id=parent_id)
            except Message.DoesNotExist:
                pass

        # Create message record (which triggers automatic XOR database encryption on save)
        msg = Message.objects.create(
            room=room,
            sender=self.user,
            content=content,
            parent_message=parent,
            message_type=message_type
        )

        # Automatically spawn system notifications for DMs
        if room.room_type == 'direct':
            from notifications.models import Notification
            recipient = room.participants.exclude(id=self.user.id).first()
            if recipient:
                Notification.objects.create(
                    recipient=recipient,
                    sender=self.user,
                    notification_type='chat_message',
                    title=f"New message from {self.user.username}",
                    message=content[:100]
                )
        
        parent_content = None
        parent_sender = None
        if msg.parent_message:
            parent_content = msg.parent_message.decrypted_content[:50]
            parent_sender = msg.parent_message.sender.username
            
        return {
            'id': msg.id,
            'created_at': msg.created_at,
            'parent_content': parent_content,
            'parent_sender': parent_sender,
            'parent_id': msg.parent_message.id if msg.parent_message else None
        }

    @database_sync_to_async
    def mark_messages_as_read(self):
        """Marks unread messages as read by generating ReadReceipt records in bulk."""
        from .models import ReadReceipt, Message
        unread_msgs = Message.objects.filter(room=self.room).exclude(sender=self.user).exclude(read_receipts__user=self.user)
        
        receipts_to_create = []
        for msg in unread_msgs:
            receipts_to_create.append(ReadReceipt(message=msg, user=self.user))
        if receipts_to_create:
            ReadReceipt.objects.bulk_create(receipts_to_create, ignore_conflicts=True)
        
        # Mark related DM notifications as read
        if self.room.room_type == 'direct':
            from notifications.models import Notification
            other_user = self.room.participants.exclude(id=self.user.id).first()
            if other_user:
                Notification.objects.filter(
                    recipient=self.user,
                    sender=other_user,
                    notification_type='chat_message',
                    is_read=False
                ).update(is_read=True)
        
        return [msg.id for msg in unread_msgs]

    @database_sync_to_async
    def update_message(self, message_id, content):
        """Edits message content. Restricts edits to sender within a 10-minute window."""
        from django.utils import timezone
        from datetime import timedelta
        msg = Message.objects.filter(pk=message_id, sender=self.user).first()
        if msg and (timezone.now() - msg.created_at) < timedelta(minutes=10):
            msg.content = content
            msg.is_edited = True
            msg.updated_at = timezone.now()
            msg.save()
            return True
        return False

    @database_sync_to_async
    def delete_message(self, message_id):
        """Soft-deletes message content and deletes attachments within a 10-minute window."""
        from django.utils import timezone
        from datetime import timedelta
        msg = Message.objects.filter(pk=message_id, sender=self.user).first()
        if msg and (timezone.now() - msg.created_at) < timedelta(minutes=10):
            msg.is_deleted = True
            msg.content = "[This message was deleted]"
            msg.save()
            # Clean up and delete attached files from disk
            for att in msg.attachments.all():
                if att.file:
                    try:
                        att.file.delete(save=False)
                    except Exception as e:
                        print(f"Error deleting file from storage: {e}")
                att.delete()
            return True
        return False

    @database_sync_to_async
    def save_reaction(self, message_id, emoji):
        """Toggles emoji reaction: creates it if missing, removes it if present."""
        from .models import MessageReaction, Message
        try:
            message = Message.objects.get(pk=message_id)
            existing = MessageReaction.objects.filter(
                message=message,
                user=self.user,
                emoji=emoji
            ).first()
            if existing:
                existing.delete()
            else:
                MessageReaction.objects.create(
                    message=message,
                    user=self.user,
                    emoji=emoji
                )
        except Exception as e:
            print(f"Error saving reaction: {e}")

    @database_sync_to_async
    def update_user_presence(self, is_online):
        """Updates user's online indicator state in the database."""
        presence, _ = UserPresence.objects.get_or_create(user=self.user)
        presence.is_online = is_online
        presence.last_seen = timezone.now()
        presence.save()

    @database_sync_to_async
    def get_room_participants(self):
        return list(self.room.participants.all())

    @database_sync_to_async
    def get_participant_room_unread(self, user):
        return Message.objects.filter(room=self.room).exclude(sender=user).exclude(read_receipts__user=user).count()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer routing dynamic personal notifications to connected user clients.
    """
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Connect user to private personal channel group
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def chat_notification(self, event):
        """Forward chat notification payloads to the browser client."""
        await self.send(text_data=json.dumps({
            'type': 'chat_notification',
            'room_id': event['room_id'],
            'sender': event['sender'],
            'content': event['content'],
            'unread_count': event['unread_count']
        }))

    async def new_notification(self, event):
        """Forward generic system notifications to the browser client."""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'unread_count': event['unread_count'],
            'notification': event['notification']
        }))


class DummyConsumer(AsyncWebsocketConsumer):
    """
    Dummy fallback socket consumer.
    Accepts scanner connections and closes them immediately to prevent connection hanging errors.
    """
    async def connect(self):
        await self.accept()
        await self.close(code=4000)
