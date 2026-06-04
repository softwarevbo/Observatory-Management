from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from accounts.models import User
from django.utils import timezone
from .models import ChatRoom, Message, UserPresence, ChatAttachment, ChatClear

def get_room_group_name(room):
    return f"chat_{room.room_id}"

@login_required
def chat_home(request):
    # Fetch all rooms the user is part of, sorted by the latest message or update time
    rooms = ChatRoom.objects.filter(participants=request.user).annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=models.Count('messages')
    ).filter(
        models.Q(room_type='group') | models.Q(msg_count__gt=0)
    ).order_by(models.F('last_msg_time').desc(nulls_last=True), '-updated_at').distinct()
    
    # Pre-fetch last messages for snippets and calculate unread counts
    for room in rooms:
        room.last_msg = room.messages.order_by('-created_at').first()
        room.unread_count = room.messages.exclude(sender=request.user).exclude(read_receipts__user=request.user).count()
    
    # Identify users with existing DM rooms to avoid duplicates in sidebar
    dm_rooms = ChatRoom.objects.filter(participants=request.user, room_type='direct').annotate(
        msg_count=models.Count('messages')
    ).filter(msg_count__gt=0)
    has_self_dm = ChatRoom.objects.filter(name=f"DM-{request.user.id}-{request.user.id}").exists()
    dm_user_ids = list(User.objects.filter(chat_rooms__in=dm_rooms).exclude(id=request.user.id).values_list('id', flat=True))
    
    # Fetch users for starting NEW DMs (include self only if self-DM doesn't exist yet)
    if has_self_dm:
        users = User.objects.exclude(id=request.user.id).exclude(id__in=dm_user_ids).select_related('presence')
    else:
        users = User.objects.exclude(id__in=dm_user_ids).select_related('presence')
    
    return render(request, 'chat/main_chat.html', {
        'rooms': rooms,
        'users': users
    })

@login_required
def create_group(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        participant_ids = request.POST.getlist('participants')
        
        room = ChatRoom.objects.create(
            name=name,
            room_type='group',
            created_by=request.user
        )
        room.participants.add(request.user)
        if participant_ids:
            room.participants.add(*participant_ids)
            
        return redirect('chat:home')
        
    users = User.objects.exclude(id=request.user.id)
    return render(request, 'chat/create_group.html', {
        'users': users
    })

@login_required
def search_messages(request):
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'results': []})
        
    messages_qs = Message.objects.filter(room__participants=request.user)
    
    room_id = request.GET.get('room_id', '')
    if room_id:
        if room_id.startswith('DM-'):
            participant_id = room_id.split('-')[1]
            room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
            messages_qs = messages_qs.filter(room__name=room_name)
        else:
            messages_qs = messages_qs.filter(room__room_id=room_id)
            
    messages = messages_qs.select_related('room', 'sender').order_by('-created_at')[:1000]
    
    msgs_data = []
    query_lower = query.lower()
    for m in messages:
        dec_content = m.decrypted_content
        if query_lower in dec_content.lower():
            room_name = m.room.name or "Group Chat"
            room_type = m.room.room_type
            
            if room_type == 'direct':
                other_user = m.room.participants.exclude(id=request.user.id).first()
                room_name = other_user.username if other_user else "Direct Message"
                
            msgs_data.append({
                'id': m.id,
                'sender': m.sender.username,
                'content': dec_content,
                'timestamp': m.created_at.strftime('%Y-%m-%d %H:%M'),
                'room_name': room_name,
                'room_id': str(m.room.room_id),
                'room_type': room_type
            })
            if len(msgs_data) >= 50:
                break
    
    return JsonResponse({'results': msgs_data})

@login_required
def project_chat(request, project_id):
    # Logic for project specific chat
    return render(request, 'chat/main_chat.html')

@login_required
def get_messages(request, room_id):
    import uuid
    room = None
    try:
        # Try UUID first
        val = uuid.UUID(room_id)
        room = ChatRoom.objects.get(room_id=val)
    except (ValueError, ChatRoom.DoesNotExist):
        # Fallback to name (simplified)
        if room_id == 'general':
            room = ChatRoom.objects.filter(name='general').first()
        elif room_id.startswith('DM-'):
            participant_id = room_id.split('-')[1]
            try:
                other_user = User.objects.get(id=participant_id)
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
                # Use filter+first to survive duplicate rows in DB
                room = ChatRoom.objects.filter(name=room_name).order_by('pk').first()
                if not room:
                    room = ChatRoom.objects.create(name=room_name, room_type='direct')
                if not room.participants.filter(id=request.user.id).exists():
                    room.participants.add(request.user)
                if not room.participants.filter(id=other_user.id).exists():
                    room.participants.add(other_user)
            except User.DoesNotExist:
                pass
    
    if not room:
        if room_id.startswith('DM-'):
            participant_id = room_id.split('-')[1]
            try:
                other_user = User.objects.get(id=participant_id)
                participants_data = [
                    {'id': request.user.id, 'username': request.user.username, 'profile_picture': request.user.profile_picture.url if request.user.profile_picture else None, 'is_online': True},
                    {'id': other_user.id, 'username': other_user.username, 'profile_picture': other_user.profile_picture.url if other_user.profile_picture else None, 'is_online': getattr(other_user, 'presence', None).is_online if getattr(other_user, 'presence', None) else False}
                ]
                return JsonResponse({'messages': [], 'participants': participants_data, 'room_type': 'direct'})
            except User.DoesNotExist:
                return JsonResponse({'messages': [], 'error': 'User not found'}, status=404)
        return JsonResponse({'messages': [], 'participants': [], 'room_type': 'group'})
        
    # Check if user cleared this chat
    clear_history = ChatClear.objects.filter(user=request.user, room=room).first()
    
    messages_query = Message.objects.filter(room=room)
    if clear_history:
        messages_query = messages_query.filter(created_at__gt=clear_history.cleared_at)
        
    messages = messages_query.prefetch_related('reactions', 'attachments', 'read_receipts').order_by('created_at')[:100]
    msgs_data = [{
        'id': m.id,
        'sender': m.sender.username,
        'sender_avatar': m.sender.profile_picture.url if m.sender.profile_picture else None,
        'content': m.decrypted_content,
        'timestamp': m.created_at.strftime('%H:%M'),
        'raw_timestamp': m.created_at.isoformat(),
        'message_type': m.message_type,
        'file_url': m.attachments.first().file.url if m.message_type == 'file' and m.attachments.exists() else None,
        'file_name': m.attachments.first().decrypted_file_name if m.message_type == 'file' and m.attachments.exists() else None,
        'file_type': m.attachments.first().file_type if m.message_type == 'file' and m.attachments.exists() else None,
        'parent_content': m.parent_message.decrypted_content[:50] if m.parent_message else None,
        'parent_sender': m.parent_message.sender.username if m.parent_message else None,
        'parent_id': m.parent_message.id if m.parent_message else None,
        'is_seen': m.read_receipts.exclude(user=m.sender).exists() if m.room.room_type == 'direct' else False,
        'reactions': [{'emoji': r.emoji, 'user': r.user.username} for r in m.reactions.all()],
        'is_edited': m.is_edited,
        'is_deleted': m.is_deleted
    } for m in messages]
    
    participants_data = [{
        'id': p.id,
        'username': p.username,
        'profile_picture': p.profile_picture.url if p.profile_picture else None,
        'is_online': getattr(p, 'presence', None).is_online if getattr(p, 'presence', None) else False
    } for p in room.participants.all()]
    
    return JsonResponse({
        'messages': msgs_data,
        'participants': participants_data,
        'room_name': room.name or "Group",
        'room_type': room.room_type,
        'room_id': str(room.room_id),
        'created_by': room.created_by.username if room.created_by else None
    })

@login_required
@csrf_exempt
def upload_chat_file(request):
    if request.method == 'POST':
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files and request.FILES.get('file'):
            files = [request.FILES.get('file')]
            
        if not files:
            return JsonResponse({'status': 'error', 'message': 'No files provided'}, status=400)
            
        room_id = request.POST.get('room_id')
        try:
            # Handle DM room_id format
            actual_room_id = room_id
            if str(room_id).startswith('DM-'):
                # For DMs, find or create the room using standardized name lookup
                participant_id = room_id.split('-')[1]
                other_user = User.objects.get(id=participant_id)
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
                room = ChatRoom.objects.filter(name=room_name).order_by('pk').first()
                if not room:
                    room = ChatRoom.objects.create(name=room_name, room_type='direct')
                if not room.participants.filter(id=request.user.id).exists():
                    room.participants.add(request.user)
                if not room.participants.filter(id=other_user.id).exists():
                    room.participants.add(other_user)
                actual_room_id = room.room_id
            
            room = ChatRoom.objects.get(room_id=actual_room_id)
            
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            group_name = get_room_group_name(room)
            
            uploaded_results = []
            for uploaded_file in files:
                message = Message.objects.create(
                    room=room,
                    sender=request.user,
                    content=f"Sent a file: {uploaded_file.name}",
                    message_type='file'
                )
                
                attachment = ChatAttachment.objects.create(
                    message=message,
                    file=uploaded_file,
                    file_name=uploaded_file.name,
                    file_type=uploaded_file.content_type,
                    file_size=uploaded_file.size
                )
                
                # Broadcast the message to all participants in the group
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'chat_message',
                            'id': message.id,
                            'message': message.decrypted_content,
                            'sender': request.user.username,
                            'sender_avatar': request.user.profile_picture.url if request.user.profile_picture else None,
                            'timestamp': message.created_at.strftime('%H:%M'),
                            'raw_timestamp': message.created_at.isoformat(),
                            'message_type': 'file',
                            'file_url': attachment.file.url,
                            'file_name': attachment.decrypted_file_name,
                            'file_type': attachment.file_type,
                            'room_id': room_id
                        }
                    )
                
                uploaded_results.append({
                    'file_url': attachment.file.url,
                    'file_name': attachment.decrypted_file_name,
                    'file_type': attachment.file_type,
                    'message_id': message.id
                })
                
            return JsonResponse({
                'status': 'success',
                'files': uploaded_results
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def clear_chat(request, room_id):
    try:
        import uuid
        try:
            val = uuid.UUID(room_id)
            room = ChatRoom.objects.get(room_id=val)
        except (ValueError, ChatRoom.DoesNotExist):
            # Try DM search
            if room_id.startswith('DM-'):
                participant_id = room_id.split('-')[1]
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
                room = ChatRoom.objects.filter(name=room_name).first()
            else:
                return JsonResponse({'status': 'error', 'message': 'Room not found'}, status=404)
        
        if not room:
             return JsonResponse({'status': 'error', 'message': 'Room not found'}, status=404)

        ChatClear.objects.update_or_create(
            user=request.user,
            room=room,
            defaults={'cleared_at': timezone.now()}
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def api_quick_chat_list(request):
    # Direct chat rooms map, unread counts, and last message time
    direct_rooms = ChatRoom.objects.filter(participants=request.user, room_type='direct').annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=models.Count('messages')
    ).filter(msg_count__gt=0).prefetch_related('participants')
    dm_room_map = {}
    dm_unread_counts = {}
    dm_last_msg_time = {}
    
    # Get user's clear history to hide cleared chats without new messages
    clear_history = dict(ChatClear.objects.filter(user=request.user).values_list('room_id', 'cleared_at'))
    
    # Handle self-chat direct room map
    self_room = ChatRoom.objects.filter(name=f"DM-{request.user.id}-{request.user.id}").annotate(
        last_msg_time=models.Max('messages__created_at')
    ).first()
    if self_room:
        dm_room_map[request.user.id] = str(self_room.room_id)
        unread = self_room.messages.exclude(sender=request.user).exclude(read_receipts__user=request.user).count()
        dm_unread_counts[str(self_room.room_id)] = unread
        dm_last_msg_time[str(self_room.room_id)] = self_room.last_msg_time

    for room in direct_rooms:
        cleared_at = clear_history.get(room.room_id)
        if cleared_at and room.last_msg_time and room.last_msg_time <= cleared_at:
            continue
            
        other_user = room.participants.exclude(id=request.user.id).first()
        if other_user:
            dm_room_map[other_user.id] = str(room.room_id)
            unread = room.messages.exclude(sender=request.user).exclude(read_receipts__user=request.user)
            if cleared_at:
                unread = unread.filter(created_at__gt=cleared_at)
            dm_unread_counts[str(room.room_id)] = unread.count()
            dm_last_msg_time[str(room.room_id)] = room.last_msg_time
            
    all_users = User.objects.select_related('presence').order_by('username')
        
    peoples = []
    for u in all_users:
        room_id = dm_room_map.get(u.id)
        unread = dm_unread_counts.get(room_id, 0) if room_id else 0
        last_time = dm_last_msg_time.get(room_id) if room_id else None
        is_online = getattr(u, 'presence', None).is_online if getattr(u, 'presence', None) else False
        avatar_url = u.profile_picture.url if u.profile_picture else f"https://ui-avatars.com/api/?name={u.username}&background=random&size=40&bold=true"
        display_name = u.display_name
        if u.id == request.user.id:
            display_name += " (You)"
        peoples.append({
            'id': u.id,
            'username': u.username,
            'display_name': display_name,
            'room_id': room_id or f"DM-{u.id}",
            'is_online': is_online if u.id != request.user.id else True,
            'avatar_url': avatar_url,
            'unread_count': unread,
            'last_msg_time': last_time.isoformat() if last_time else None,
            '_last_msg_time_obj': last_time
        })
        
    # Sort peoples: those with last_msg_time descending first, then online status, then username
    def get_peoples_sort_key(x):
        dt = x.get('_last_msg_time_obj')
        if dt:
            return (0, -dt.timestamp(), not x['is_online'], x['username'].lower())
        else:
            return (1, 0, not x['is_online'], x['username'].lower())

    peoples.sort(key=get_peoples_sort_key)
        
    # Fetch groups / projects sorted by latest message
    group_rooms = ChatRoom.objects.filter(participants=request.user).annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=models.Count('messages')
    ).filter(
        models.Q(room_type='group') | models.Q(room_type='project')
    ).order_by(models.F('last_msg_time').desc(nulls_last=True), '-updated_at').distinct()
    
    groups = []
    for room in group_rooms:
        cleared_at = clear_history.get(room.room_id)
        if cleared_at and room.last_msg_time and room.last_msg_time <= cleared_at:
            continue
            
        unread = room.messages.exclude(sender=request.user).exclude(read_receipts__user=request.user)
        if cleared_at:
            unread = unread.filter(created_at__gt=cleared_at)
        unread = unread.count()
        
        if room.room_type == 'direct':
            other_user = room.participants.exclude(id=request.user.id).first()
            if not other_user:
                other_user = request.user
            name = other_user.display_name
            if other_user == request.user:
                name += " (You)"
            avatar_url = other_user.profile_picture.url if other_user.profile_picture else f"https://ui-avatars.com/api/?name={other_user.username}&background=random&size=40&bold=true"
            is_online = getattr(other_user, 'presence', None).is_online if getattr(other_user, 'presence', None) else False
            if other_user == request.user:
                is_online = True
        else:
            name = room.name or f"Group {room.room_id}"
            avatar_url = room.room_picture.url if room.room_picture else f"https://ui-avatars.com/api/?name={room.name or 'Group'}&background=random&size=40&bold=true"
            is_online = False
            
        groups.append({
            'room_id': str(room.room_id),
            'name': name,
            'room_type': room.room_type,
            'avatar_url': avatar_url,
            'unread_count': unread,
            'is_online': is_online,
            'last_msg_time': room.last_msg_time.isoformat() if room.last_msg_time else None,
            'created_by': room.created_by.username if room.created_by else None
        })
        
    # Fetch attachments in user's rooms
    attachments = ChatAttachment.objects.filter(
        message__room__participants=request.user
    ).select_related('message', 'message__sender', 'message__room').order_by('-message__created_at')[:50]
    
    files_list = []
    for att in attachments:
        files_list.append({
            'file_name': att.file_name,
            'file_url': att.file.url,
            'file_type': att.file_type,
            'file_size': att.file_size,
            'sender': att.message.sender.username,
            'room_name': att.message.room.name or "Direct Chat",
            'timestamp': att.message.created_at.strftime('%I:%M %p')
        })

    # Total unread count
    total_unread = sum(dm_unread_counts.values()) + sum(g['unread_count'] for g in groups)
        
    return JsonResponse({
        'peoples': peoples,
        'groups': groups,
        'files': files_list,
        'total_unread': total_unread
    })

@login_required
@csrf_exempt
def forward_message(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            target_room_id = data.get('room_id')
            
            msg = Message.objects.get(pk=message_id)
            
            import uuid
            room = None
            if target_room_id.startswith('DM-'):
                participant_id = target_room_id.split('-')[1]
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
                # Use filter+first to survive duplicate rows in DB
                room = ChatRoom.objects.filter(name=room_name).order_by('pk').first()
                if not room:
                    room = ChatRoom.objects.create(name=room_name, room_type='direct')
                room.participants.add(request.user)
                try:
                    other_user = User.objects.get(id=participant_id)
                    room.participants.add(other_user)
                except User.DoesNotExist:
                    pass
            else:
                room = ChatRoom.objects.get(room_id=uuid.UUID(target_room_id))
                
            new_msg = Message.objects.create(
                room=room,
                sender=request.user,
                content=msg.content,
                message_type=msg.message_type
            )
            
            first_att = None
            if msg.message_type == 'file':
                for att in msg.attachments.all():
                    first_att = ChatAttachment.objects.create(
                        message=new_msg,
                        file=att.file,
                        file_name=att.file_name,
                        file_type=att.file_type,
                        file_size=att.file_size
                    )
            
            # Broadcast to target group
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            room_group_name = get_room_group_name(room)
            
            broadcast_data = {
                'type': 'chat_message',
                'room_id': str(room.room_id),
                'id': new_msg.id,
                'message': new_msg.decrypted_content,
                'sender': request.user.username,
                'sender_avatar': request.user.profile_picture.url if request.user.profile_picture else None,
                'timestamp': new_msg.created_at.strftime('%H:%M'),
                'raw_timestamp': new_msg.created_at.isoformat(),
                'message_type': new_msg.message_type,
                'file_url': first_att.file.url if first_att else None,
                'file_name': first_att.decrypted_file_name if first_att else None,
                'file_type': first_att.file_type if first_att else None,
            }
            
            async_to_sync(channel_layer.group_send)(room_group_name, broadcast_data)
            
            # Send chat notification to other participants' personal groups
            try:
                participants = list(room.participants.all())
                for p in participants:
                    if p.id != request.user.id:
                        unread_count = Message.objects.filter(room=room).exclude(sender=p).exclude(read_receipts__user=p).count()
                        async_to_sync(channel_layer.group_send)(
                            f"user_{p.id}",
                            {
                                "type": "chat_notification",
                                "room_id": str(room.room_id),
                                "sender": request.user.username,
                                "content": new_msg.decrypted_content if new_msg.message_type == 'text' else 'File',
                                "unread_count": unread_count
                            }
                        )
            except Exception as e:
                print(f"Error sending forward chat notification: {e}")

            return JsonResponse({
                'status': 'success',
                'new_message_id': new_msg.id,
                'room_id': str(room.room_id),
                'content': new_msg.content if new_msg.message_type == 'text' else 'File'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
@csrf_exempt
def bulk_delete_messages(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            message_ids = data.get('message_ids', [])
            if not message_ids:
                return JsonResponse({'status': 'error', 'message': 'No message IDs provided'}, status=400)

            # Only delete messages sent by the current user within 10 minutes
            from datetime import timedelta
            ten_minutes_ago = timezone.now() - timedelta(minutes=10)
            messages_qs = Message.objects.filter(
                pk__in=message_ids,
                sender=request.user,
                created_at__gte=ten_minutes_ago,
                is_deleted=False
            )
            deleted_ids = list(messages_qs.values_list('pk', flat=True))
            
            # Clean up and delete attachments
            for msg in messages_qs:
                for att in msg.attachments.all():
                    if att.file:
                        try:
                            att.file.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting file in bulk delete: {e}")
                    att.delete()
            
            messages_qs.update(is_deleted=True, content='This message was deleted')

            # Broadcast deletion to each affected room
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                processed_rooms = set()
                for msg in Message.objects.filter(pk__in=deleted_ids).select_related('room'):
                    room_group = get_room_group_name(msg.room)
                    if room_group not in processed_rooms:
                        processed_rooms.add(room_group)
                    async_to_sync(channel_layer.group_send)(room_group, {
                        'type': 'message_deleted',
                        'message_id': msg.pk
                    })

            return JsonResponse({'status': 'success', 'deleted_ids': deleted_ids})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
@csrf_exempt
def delete_group(request, room_id):
    import uuid
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type == 'group':
            if room.created_by and request.user != room.created_by:
                return JsonResponse({'status': 'error', 'message': 'Only the group creator can delete this group'}, status=403)
            if not room.created_by and request.user not in room.participants.all():
                return JsonResponse({'status': 'error', 'message': 'Not allowed'}, status=403)
            room.participants.clear()
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Not allowed or not a group'}, status=403)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
