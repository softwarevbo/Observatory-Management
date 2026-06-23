import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from inventory.models import InventoryUser, InventoryMessage

"""
This module contains HTTP-based chat view endpoints for Inventory Users.
Since InventoryUsers are not standard Django auth users, WebSockets cannot
authenticate them via Channels. Instead we use a lightweight HTTP polling
architecture with a JSON API (typically polled every 3-5 seconds by the client).
"""


def _get_inv_user(request):
    """Retrieves the current logged-in InventoryUser from session, or None."""
    inv_user_id = request.session.get("inv_user_id")
    if inv_user_id:
        try:
            return InventoryUser.objects.get(id=inv_user_id, is_active=True)
        except InventoryUser.DoesNotExist:
            pass
    if hasattr(request, "user") and request.user.is_authenticated:
        try:
            return InventoryUser.objects.get(username=request.user.username, is_active=True)
        except InventoryUser.DoesNotExist:
            role = "staff"
            if request.user.is_superuser or getattr(request.user, "role", None) == "admin":
                role = "super_admin"
            elif getattr(request.user, "role", None) == "project_manager":
                role = "branch_admin"
            try:
                inv_user = InventoryUser.objects.create(
                    username=request.user.username,
                    role=role,
                    email=request.user.email,
                    is_active=True
                )
                import uuid
                inv_user.set_password(uuid.uuid4().hex)
                return inv_user
            except Exception:
                pass
    return None


def inv_chat_users(request):
    """
    JSON API returning a list of all active inventory users with unread message counts.
    Used to populate the contact list in the inventory chat popup.
    """
    me = _get_inv_user(request)
    if not me:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    users = InventoryUser.objects.filter(is_active=True).exclude(id=me.id).order_by("username")

    # Compute unread counts per sender in one query
    unread_qs = InventoryMessage.objects.filter(recipient=me, is_read=False).values("sender_id")
    unread_map = {}
    for row in unread_qs:
        sid = row["sender_id"]
        unread_map[sid] = unread_map.get(sid, 0) + 1

    # Compute last message timestamps per conversation
    last_msg_map = {}
    msgs = InventoryMessage.objects.filter(
        sender__in=users, recipient=me
    ).order_by("created_at").values("sender_id", "created_at")
    for m in msgs:
        last_msg_map[m["sender_id"]] = m["created_at"]
    msgs2 = InventoryMessage.objects.filter(
        sender=me, recipient__in=users
    ).order_by("created_at").values("recipient_id", "created_at")
    for m in msgs2:
        rid = m["recipient_id"]
        if rid not in last_msg_map or m["created_at"] > last_msg_map[rid]:
            last_msg_map[rid] = m["created_at"]

    contacts = []
    for u in users:
        contacts.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.get_role_display(),
            "branch": u.branch.name if u.branch else None,
            "unread": unread_map.get(u.id, 0),
            "last_msg_time": last_msg_map[u.id].isoformat() if u.id in last_msg_map else None,
        })

    # Sort: conversations with messages first (by latest message time), then alphabetical
    contacts.sort(key=lambda c: (c["last_msg_time"] is None, -(len(c["last_msg_time"] or "")), c["username"].lower()))

    total_unread = sum(unread_map.values())
    return JsonResponse({"contacts": contacts, "total_unread": total_unread, "my_id": me.id})


def inv_chat_messages(request, user_id):
    """
    JSON API returning the message history between the current user and the given user.
    Also marks the conversation as read.
    """
    me = _get_inv_user(request)
    if not me:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    try:
        other = InventoryUser.objects.get(id=user_id)
    except InventoryUser.DoesNotExist:
        return JsonResponse({"error": "user not found"}, status=404)

    # Fetch conversation (both directions) limited to last 100 messages
    msgs = InventoryMessage.objects.filter(
        sender__in=[me, other], recipient__in=[me, other]
    ).select_related("sender").order_by("created_at")[:100]

    # Mark messages from other as read
    InventoryMessage.objects.filter(sender=other, recipient=me, is_read=False).update(is_read=True)

    data = []
    for m in msgs:
        data.append({
            "id": m.id,
            "sender_id": m.sender.id,
            "sender": m.sender.username,
            "content": m.content,
            "is_mine": m.sender_id == me.id,
            "timestamp": m.created_at.strftime("%H:%M"),
            "raw_timestamp": m.created_at.isoformat(),
        })

    return JsonResponse({
        "messages": data,
        "other_user": {
            "id": other.id,
            "username": other.username,
            "display_name": other.display_name,
            "role": other.get_role_display(),
            "branch": other.branch.name if other.branch else None,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def inv_chat_send(request, user_id):
    """
    JSON API endpoint to send a message from the current inventory user to the given user.
    """
    me = _get_inv_user(request)
    if not me:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    try:
        other = InventoryUser.objects.get(id=user_id)
    except InventoryUser.DoesNotExist:
        return JsonResponse({"error": "user not found"}, status=404)

    try:
        body = json.loads(request.body)
        content = (body.get("content") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        content = (request.POST.get("content") or "").strip()

    if not content:
        return JsonResponse({"error": "empty message"}, status=400)

    msg = InventoryMessage.objects.create(sender=me, recipient=other, content=content)
    return JsonResponse({
        "id": msg.id,
        "sender_id": me.id,
        "sender": me.username,
        "content": msg.content,
        "is_mine": True,
        "timestamp": msg.created_at.strftime("%H:%M"),
        "raw_timestamp": msg.created_at.isoformat(),
    })


def inv_chat_poll(request, user_id):
    """
    JSON API polling endpoint returning only messages newer than `after_id`.
    Clients call this every ~3 seconds to receive real-time updates without WebSockets.
    """
    me = _get_inv_user(request)
    if not me:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    try:
        other = InventoryUser.objects.get(id=user_id)
    except InventoryUser.DoesNotExist:
        return JsonResponse({"error": "user not found"}, status=404)

    after_id = request.GET.get("after_id", 0)
    try:
        after_id = int(after_id)
    except (TypeError, ValueError):
        after_id = 0

    msgs = InventoryMessage.objects.filter(
        sender__in=[me, other],
        recipient__in=[me, other],
        id__gt=after_id,
    ).select_related("sender").order_by("created_at")

    # Mark new messages from other as read
    InventoryMessage.objects.filter(sender=other, recipient=me, is_read=False).update(is_read=True)

    data = []
    for m in msgs:
        data.append({
            "id": m.id,
            "sender_id": m.sender.id,
            "sender": m.sender.username,
            "content": m.content,
            "is_mine": m.sender_id == me.id,
            "timestamp": m.created_at.strftime("%H:%M"),
            "raw_timestamp": m.created_at.isoformat(),
        })

    return JsonResponse({"messages": data})
