from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from accounts.models import User
from django.utils import timezone
from .models import ChatRoom, Message, UserPresence, ChatAttachment, ChatClear
from .utils import get_avatar_svg

"""
This module contains HTTP view handlers for the chat application workspace.
Most views are decorated with `@login_required` to protect against unauthorized queries.

Many views act as JSON API endpoints consumed by frontend JavaScript code, 
enabling dynamic message loading, file uploads, text searches, and history clears.
"""

def get_room_group_name(room):
    """Utility helper to resolve standard group channel name string."""
    return f"chat_{room.room_id}"


def can_manage_room_members(room, user):
    """
    Checks if a user has permission to manage members in a chat room.
    Permits room creator, project managers (for project rooms), and system admins.
    """
    if user.is_admin:
        return True
    if room.room_type == 'project' and room.project:
        # Check if user is a manager of the associated project
        if room.project.managers.filter(pk=user.pk).exists():
            return True
    if room.created_by and room.created_by == user:
        return True
    return False


@login_required
def chat_home(request):
    """
    Renders the main chat console dashboard.
    Annotates rooms with last message times, calculates unread counts,
    and returns a filtered user list to initiate new direct conversations.
    """
    from django.db.models.functions import Coalesce
    
    # 1. Define subquery for unread counts (messages where sender is not request.user and request.user hasn't read it)
    unread_subquery = Message.objects.filter(
        room=models.OuterRef('pk')
    ).exclude(
        sender=request.user
    ).exclude(
        read_receipts__user=request.user
    ).values('room').annotate(c=models.Count('id')).values('c')

    # 2. Define subquery for message counts to filter out empty DMs without duplicate join multiplication
    msg_count_subquery = Message.objects.filter(
        room=models.OuterRef('pk')
    ).values('room').annotate(c=models.Count('id')).values('c')

    # Fetch all active rooms the user participates in.
    # Annotate with the latest message time and subqueries to sort rooms chronologically.
    rooms = ChatRoom.objects.filter(participants=request.user).annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=Coalesce(models.Subquery(msg_count_subquery, output_field=models.IntegerField()), 0),
        unread_count=Coalesce(models.Subquery(unread_subquery, output_field=models.IntegerField()), 0)
    ).filter(
        # Group chats show immediately; DMs only show if they contain at least one message.
        models.Q(room_type='group') | models.Q(msg_count__gt=0)
    ).order_by(models.F('last_msg_time').desc(nulls_last=True), '-updated_at').distinct()
    
    # Fetch latest messages in bulk to prevent N+1 queries
    last_msg_ids = Message.objects.filter(
        room__participants=request.user
    ).values('room').annotate(
        last_id=models.Max('id')
    ).values_list('last_id', flat=True)
    
    last_msgs = {m.room_id: m for m in Message.objects.filter(id__in=last_msg_ids).select_related('sender')}
    
    # Pre-fetch snippets and map unread counts
    for room in rooms:
        room.last_msg = last_msgs.get(room.room_id)

    
    # Identify user IDs who already have active DM rooms with this user to avoid duplicates in sidebar lists
    dm_rooms = ChatRoom.objects.filter(participants=request.user, room_type='direct').annotate(
        msg_count=models.Count('messages')
    ).filter(msg_count__gt=0)
    has_self_dm = ChatRoom.objects.filter(name=f"DM-{request.user.id}-{request.user.id}").exists()
    dm_user_ids = list(User.objects.filter(chat_rooms__in=dm_rooms).exclude(id=request.user.id).values_list('id', flat=True))
    
    # Fetch users list for initiating new DM conversations (excluding current contacts)
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
    """
    Handles group chat room creation.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        participant_ids = request.POST.getlist('participants')
        
        room = ChatRoom.objects.create(
            name=name,
            room_type='group',
            created_by=request.user
        )
        # Add creator and selected participants
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
    """
    AJAX endpoint returning matching messages for a search query.
    Performs case-insensitive checks on decrypted content values.
    """
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'results': []})
        
    # Restrict search range to rooms the user participates in
    messages_qs = Message.objects.filter(room__participants=request.user)
    
    # Filter search by a specific room context if specified
    room_id = request.GET.get('room_id', '')
    if room_id:
        if room_id.startswith('DM-'):
            participant_id = room_id.split('-')[1]
            room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
            messages_qs = messages_qs.filter(room__name=room_name)
        else:
            messages_qs = messages_qs.filter(room__room_id=room_id)
            
    # Load relationships to optimize database lookup
    messages = messages_qs.select_related('room', 'sender').order_by('-created_at')[:1000]
    
    msgs_data = []
    query_lower = query.lower()
    for m in messages:
        # Decrypt message content on the fly to check for string matching
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
            # Limit search results to 50 items for speed
            if len(msgs_data) >= 50:
                break
    
    return JsonResponse({'results': msgs_data})


@login_required
def project_chat(request, project_id):
    """
    Renders main chat dashboard focused on a specific project room.
    """
    return render(request, 'chat/main_chat.html')


@login_required
def get_messages(request, room_id):
    """
    REST API returning message logs and participants list for a chat room.
    Filters out messages sent before the user's history clear timestamp.
    """
    import uuid
    room = None
    try:
        # Resolve target room by UUID key first
        val = uuid.UUID(room_id)
        room = ChatRoom.objects.get(room_id=val)
    except (ValueError, ChatRoom.DoesNotExist):
        # Fallback lookups
        if room_id == 'general':
            room = ChatRoom.objects.filter(name='general').first()
        elif room_id.startswith('DM-'):
            # Standard DM path (creates room on the fly if not existing yet)
            participant_id = room_id.split('-')[1]
            try:
                other_user = User.objects.get(id=participant_id)
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
                room = ChatRoom.objects.filter(name=room_name).order_by('pk').first()
                if not room:
                    room = ChatRoom.objects.create(name=room_name, room_type='direct')
                if not room.participants.filter(id=request.user.id).exists():
                    room.participants.add(request.user)
                if not room.participants.filter(id=other_user.id).exists():
                    room.participants.add(other_user)
            except User.DoesNotExist:
                pass
    
    # If room is not persisted yet (e.g. initial DM click), return placeholders structure
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
        
    # Check if the user has cleared logs history in this room
    clear_history = ChatClear.objects.filter(user=request.user, room=room).first()
    
    messages_query = Message.objects.filter(room=room)
    # Hide messages created before user's clear timestamp
    if clear_history:
        messages_query = messages_query.filter(created_at__gt=clear_history.cleared_at)
        
    # Prefetch relations to prevent database overheads and fetch the latest 100 messages chronologically
    messages = list(messages_query.prefetch_related('reactions', 'attachments', 'read_receipts').order_by('-created_at')[:100])[::-1]
    
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
        'created_by': room.created_by.username if room.created_by else None,
        'is_group_admin': can_manage_room_members(room, request.user)
    })


@login_required
@csrf_exempt
def upload_chat_file(request):
    """
    REST API endpoint managing file attachment uploads in chat messages.
    Saves file meta descriptors to DB, triggers file saving to media directories, 
    and broadcasts details through Channel Group layer.
    """
    if request.method == 'POST':
        # Retrieve uploaded file list
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files and request.FILES.get('file'):
            files = [request.FILES.get('file')]
            
        if not files:
            return JsonResponse({'status': 'error', 'message': 'No files provided'}, status=400)
            
        room_id = request.POST.get('room_id')
        try:
            actual_room_id = room_id
            # Resolve DM target room context if required
            if str(room_id).startswith('DM-'):
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
            
            # Retrieve Channel Layer broadcast engine
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            group_name = get_room_group_name(room)
            uploaded_results = []
            
            for uploaded_file in files:
                # 1. Create companion message record
                message = Message.objects.create(
                    room=room,
                    sender=request.user,
                    content=f"Sent a file: {uploaded_file.name}",
                    message_type='file'
                )
                
                # 2. Save file attachment details
                attachment = ChatAttachment.objects.create(
                    message=message,
                    file=uploaded_file,
                    file_name=uploaded_file.name,
                    file_type=uploaded_file.content_type,
                    file_size=uploaded_file.size
                )
                
                # 3. Broadcast update to room participants
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
    """
    Clears message logs visibility. Registers a ChatClear record to set
    a start boundary for user visibility queries.
    """
    try:
        import uuid
        try:
            val = uuid.UUID(room_id)
            room = ChatRoom.objects.get(room_id=val)
        except (ValueError, ChatRoom.DoesNotExist):
            # Try DM search lookup
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
    """
    REST API returning sorted groups, DM lists, online presence status indicators, 
    unread notifications count summary, and shared attachments lists.
    """
    from django.db.models.functions import Coalesce
    
    # Define subquery to calculate message counts safely without Cartesian products
    msg_count_subquery = Message.objects.filter(
        room=models.OuterRef('pk')
    ).values('room').annotate(c=models.Count('id')).values('c')

    # 1. Fetch DM rooms with messages
    direct_rooms = ChatRoom.objects.filter(participants=request.user, room_type='direct').annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=Coalesce(models.Subquery(msg_count_subquery, output_field=models.IntegerField()), 0)
    ).filter(msg_count__gt=0).prefetch_related('participants')
    
    dm_room_map = {}
    dm_unread_counts = {}
    dm_last_msg_time = {}
    
    # Retrieve clear timestamps to filter out cleared logs
    clear_history = dict(ChatClear.objects.filter(user=request.user).values_list('room_id', 'cleared_at'))
    
    # Fetch all unread messages for the user across all rooms in a single bulk query
    unread_messages = Message.objects.filter(
        room__participants=request.user
    ).exclude(
        sender=request.user
    ).exclude(
        read_receipts__user=request.user
    ).values('room_id', 'created_at')
    
    # Group unread counts in Python to avoid N+1 queries
    unread_counts_map = {}
    for msg in unread_messages:
        room_uuid = str(msg['room_id'])
        cleared_at = clear_history.get(msg['room_id'])
        if cleared_at and msg['created_at'] <= cleared_at:
            continue
        unread_counts_map[room_uuid] = unread_counts_map.get(room_uuid, 0) + 1

    # Resolve self-chat DM configurations
    self_room = ChatRoom.objects.filter(name=f"DM-{request.user.id}-{request.user.id}").annotate(
        last_msg_time=models.Max('messages__created_at')
    ).first()
    if self_room:
        dm_room_map[request.user.id] = str(self_room.room_id)
        dm_unread_counts[str(self_room.room_id)] = unread_counts_map.get(str(self_room.room_id), 0)
        dm_last_msg_time[str(self_room.room_id)] = self_room.last_msg_time

    # Populate DM mappings and unread totals
    for room in direct_rooms:
        cleared_at = clear_history.get(room.room_id)
        if cleared_at and room.last_msg_time and room.last_msg_time <= cleared_at:
            continue
            
        other_user = room.participants.exclude(id=request.user.id).first()
        if other_user:
            dm_room_map[other_user.id] = str(room.room_id)
            dm_unread_counts[str(room.room_id)] = unread_counts_map.get(str(room.room_id), 0)
            dm_last_msg_time[str(room.room_id)] = room.last_msg_time
            
    all_users = User.objects.select_related('presence').order_by('username')
        
    # Construct contact list elements
    peoples = []
    for u in all_users:
        room_id = dm_room_map.get(u.id)
        unread = dm_unread_counts.get(room_id, 0) if room_id else 0
        last_time = dm_last_msg_time.get(room_id) if room_id else None
        is_online = getattr(u, 'presence', None).is_online if getattr(u, 'presence', None) else False
        avatar_url = u.profile_picture.url if u.profile_picture else get_avatar_svg(u.username, u.avatar_color)
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
        
    # Sort contacts: contacts with active message exchanges display first (ordered by timestamp)
    def get_peoples_sort_key(x):
        dt = x.get('_last_msg_time_obj')
        if dt:
            return (0, -dt.timestamp(), not x['is_online'], x['username'].lower())
        else:
            return (1, 0, not x['is_online'], x['username'].lower())

    peoples.sort(key=get_peoples_sort_key)
        
    # 2. Fetch Group/Project rooms sorted by latest messages
    group_rooms = ChatRoom.objects.filter(participants=request.user).annotate(
        last_msg_time=models.Max('messages__created_at'),
        msg_count=Coalesce(models.Subquery(msg_count_subquery, output_field=models.IntegerField()), 0)
    ).filter(
        models.Q(room_type='group') | models.Q(room_type='project')
    ).order_by(models.F('last_msg_time').desc(nulls_last=True), '-updated_at').distinct()
    
    groups = []
    for room in group_rooms:
        cleared_at = clear_history.get(room.room_id)
        if cleared_at and room.last_msg_time and room.last_msg_time <= cleared_at:
            continue
            
        unread = unread_counts_map.get(str(room.room_id), 0)
        
        if room.room_type == 'direct':
            other_user = room.participants.exclude(id=request.user.id).first()
            if not other_user:
                other_user = request.user
            name = other_user.display_name
            if other_user == request.user:
                name += " (You)"
            avatar_url = other_user.profile_picture.url if other_user.profile_picture else get_avatar_svg(other_user.username, other_user.avatar_color)
            is_online = getattr(other_user, 'presence', None).is_online if getattr(other_user, 'presence', None) else False
            if other_user == request.user:
                is_online = True
        else:
            name = room.name or f"Group {room.room_id}"
            avatar_url = room.room_picture.url if room.room_picture else get_avatar_svg(room.name or 'Group')
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

        
    # 3. Fetch shared attachments listing (latest 50 files)
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

    # Compute grand total of unread alerts
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
    """
    Copies a message payload (including attachments if present) and posts it
    into a target room, broadcasting it to group sockets.
    """
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            target_room_id = data.get('room_id')
            
            msg = Message.objects.get(pk=message_id)
            
            # Resolve target room
            import uuid
            room = None
            if target_room_id.startswith('DM-'):
                participant_id = target_room_id.split('-')[1]
                room_name = f"DM-{min(str(request.user.id), str(participant_id))}-{max(str(request.user.id), str(participant_id))}"
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
                
            # Create forwarded message record
            new_msg = Message.objects.create(
                room=room,
                sender=request.user,
                content=msg.content,
                message_type=msg.message_type
            )
            
            first_att = None
            # Copy attachments if message represents a file
            if msg.message_type == 'file':
                for att in msg.attachments.all():
                    first_att = ChatAttachment.objects.create(
                        message=new_msg,
                        file=att.file,
                        file_name=att.file_name,
                        file_type=att.file_type,
                        file_size=att.file_size
                    )
            
            # Broadcast the forward message event to the target room
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
            
            # Alert other participants of the forwarded message
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
    """
    Deletes multiple messages simultaneously.
    Restricts operations to sender-owned messages sent within a 10-minute window.
    """
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            message_ids = data.get('message_ids', [])
            if not message_ids:
                return JsonResponse({'status': 'error', 'message': 'No message IDs provided'}, status=400)
 
            # Apply safety timing guard (10 minutes)
            from datetime import timedelta
            ten_minutes_ago = timezone.now() - timedelta(minutes=10)
            messages_qs = Message.objects.filter(
                pk__in=message_ids,
                sender=request.user,
                created_at__gte=ten_minutes_ago,
                is_deleted=False
            )
            deleted_ids = list(messages_qs.values_list('pk', flat=True))
            
            # Clean up and delete attached files from disk
            for msg in messages_qs:
                for att in msg.attachments.all():
                    if att.file:
                        try:
                            att.file.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting file in bulk delete: {e}")
                    att.delete()
            
            # Update message state (soft-deletion text)
            messages_qs.update(is_deleted=True, content='This message was deleted')
 
            # Broadcast deletion notifications to affected rooms
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
    """
    Clears all participants out of a group room, effectively destroying it.
    Restricted to group creator only.
    """
    import uuid
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type == 'group':
            if room.created_by and request.user != room.created_by:
                return JsonResponse({'status': 'error', 'message': 'Only the group creator can delete this group'}, status=403)
            if not room.created_by and request.user not in room.participants.all():
                return JsonResponse({'status': 'error', 'message': 'Not allowed'}, status=403)
            # Remove all participants
            room.participants.clear()
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Not allowed or not a group'}, status=403)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@csrf_exempt
def leave_group(request, room_id):
    """
    Remove the current user from the group room's participants list.
    Also creates a system message and broadcasts the update.
    """
    import uuid
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type in ['group', 'project']:
            if request.user in room.participants.all():
                # Remove user
                room.participants.remove(request.user)
                
                # Create a system message
                msg = Message.objects.create(
                    room=room,
                    sender=request.user,
                    content=f"System: {request.user.username} has left the group.",
                    message_type='system'
                )
                
                # Broadcast the leave event & message
                channel_layer = get_channel_layer()
                if channel_layer:
                    group_name = f"chat_{room.room_id}"
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'chat_message',
                            'id': msg.id,
                            'message': msg.decrypted_content,
                            'sender': 'System',
                            'sender_avatar': None,
                            'timestamp': msg.created_at.strftime('%H:%M'),
                            'raw_timestamp': msg.created_at.isoformat(),
                            'message_type': 'system',
                            'room_id': str(room.room_id)
                        }
                    )
                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'You are not a member of this group'}, status=400)
        return JsonResponse({'status': 'error', 'message': 'Not a group chat'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@csrf_exempt
def remove_member(request, room_id, user_id):
    """
    Remove a specific user from the group room's participants list.
    Restricted to group creator/admin only.
    Also creates a system message and broadcasts the update.
    """
    import uuid
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type in ['group', 'project']:
            # Authorization check: only group creator can remove members
            if not can_manage_room_members(room, request.user):
                return JsonResponse({'status': 'error', 'message': 'Only the group creator/admin can remove members'}, status=403)
            
            target_user = User.objects.get(id=user_id)
            if target_user in room.participants.all():
                room.participants.remove(target_user)
                
                # Create a system message
                msg = Message.objects.create(
                    room=room,
                    sender=request.user,
                    content=f"System: {target_user.username} was removed from the group by {request.user.username}.",
                    message_type='system'
                )
                
                # Broadcast the removal & message
                channel_layer = get_channel_layer()
                if channel_layer:
                    group_name = f"chat_{room.room_id}"
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'chat_message',
                            'id': msg.id,
                            'message': msg.decrypted_content,
                            'sender': 'System',
                            'sender_avatar': None,
                            'timestamp': msg.created_at.strftime('%H:%M'),
                            'raw_timestamp': msg.created_at.isoformat(),
                            'message_type': 'system',
                            'room_id': str(room.room_id)
                        }
                    )
                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'User is not a member of this group'}, status=400)
        return JsonResponse({'status': 'error', 'message': 'Not a group chat'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def get_non_members(request, room_id):
    """
    Returns all users NOT currently in the group, so the admin can pick who to add.
    Restricted to group creator/admin only.
    """
    import uuid
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type not in ['group', 'project']:
            return JsonResponse({'status': 'error', 'message': 'Not a group chat'}, status=400)
        if not can_manage_room_members(room, request.user):
            return JsonResponse({'status': 'error', 'message': 'Only the group admin can view non-members'}, status=403)

        non_members = User.objects.exclude(
            id__in=room.participants.values_list('id', flat=True)
        ).select_related('presence')

        data = []
        for u in non_members:
            data.append({
                'id': u.id,
                'username': u.username,
                'display_name': u.display_name,
                'avatar_url': u.profile_picture.url if u.profile_picture else get_avatar_svg(u.username, u.avatar_color),
                'is_online': getattr(u, 'presence', None).is_online if getattr(u, 'presence', None) else False,
            })
        return JsonResponse({'status': 'success', 'users': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@csrf_exempt
def add_member(request, room_id, user_id):
    """
    Add a specific user to the group room's participants list.
    Restricted to group creator/admin only.
    Creates a system message and broadcasts the update via WebSocket.
    """
    import uuid
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    try:
        room = ChatRoom.objects.get(room_id=uuid.UUID(room_id))
        if room.room_type in ['group', 'project']:
            # Authorization: only group creator/admin can add members
            if not can_manage_room_members(room, request.user):
                return JsonResponse({'status': 'error', 'message': 'Only the group creator/admin can add members'}, status=403)

            target_user = User.objects.get(id=user_id)
            if target_user in room.participants.all():
                return JsonResponse({'status': 'error', 'message': 'User is already a member of this group'}, status=400)

            room.participants.add(target_user)

            # Create a system message
            msg = Message.objects.create(
                room=room,
                sender=request.user,
                content=f"System: {target_user.username} was added to the group by {request.user.username}.",
                message_type='system'
            )

            # Broadcast the addition & system message to all room participants
            channel_layer = get_channel_layer()
            if channel_layer:
                group_name = f"chat_{room.room_id}"
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'chat_message',
                        'id': msg.id,
                        'message': msg.decrypted_content,
                        'sender': 'System',
                        'sender_avatar': None,
                        'timestamp': msg.created_at.strftime('%H:%M'),
                        'raw_timestamp': msg.created_at.isoformat(),
                        'message_type': 'system',
                        'room_id': str(room.room_id)
                    }
                )
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Not a group chat'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
