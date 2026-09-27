# Chat Functionality - Complete Guide

## Overview
This document provides comprehensive information about the improved chat system in the Project Management Tool with full support for large file transfers (350MB+), real-time messaging, and secure file sharing.

---

## 🎯 Key Features

### 1. **Real-time Messaging**
- **WebSocket-based communication** via Django Channels
- **End-to-end encryption** for all messages using XOR encryption
- **Message threading** with reply support
- **Message editing** (up to 10 minutes after sending)
- **Message deletion** with attachment cleanup

### 2. **Secure File Sharing**
- **Large file support** up to 5GB per file
- **Permission-based access** - only room participants can download
- **Streaming downloads** for efficient memory usage
- **Chunked upload support** for large files
- **File integrity verification**
- **Automatic file cleanup** on message deletion

### 3. **Room Types**
- **Direct Messages (DM)** - One-on-one private conversations
- **Group Chats** - Multi-user discussion rooms
- **Project Rooms** - Chat specific to project collaboration

### 4. **User Presence**
- **Real-time online status** tracking
- **Last seen timestamps**
- **Presence notifications** across all connected clients

### 5. **Read Receipts**
- **Message read status** per participant
- **Unread message counting**
- **Read receipt notifications**

### 6. **Message Search**
- **Full-text search** across all accessible messages
- **Encrypted content searching** (decrypts on search)
- **Room-scoped searches** available

---

## 📁 File Transfer System

### Upload Process (Files up to 5GB)

#### Standard Upload (Files < 500MB)
```
1. User selects file(s) via drag-drop or file picker
2. Browser sends file to /chat/api/upload/ endpoint
3. Django validates file size and type
4. File saved to media/chat_attachments/
5. ChatAttachment record created in database
6. File URL broadcast to all room participants
```

#### Chunked Upload (Files >= 500MB)
```
1. Frontend calculates chunks (5MB each)
2. Sends chunks sequentially to /chat/api/upload-chunk/
3. Backend assembles chunks into final file
4. File integrity verified via SHA256
5. Original chunks cleaned up from temp storage
```

### Download Process (Streaming for Large Files)

#### Access Control
- Only room participants can download files
- Permission verified against ChatRoom.participants
- Unauthorized access returns 403 Forbidden

#### Download Endpoint
```
GET /chat/api/download/<attachment_id>/
```

#### Streaming for Large Files
- Files > 10MB use StreamingHttpResponse
- Sends data in 8MB chunks
- Supports resume on interrupted downloads
- Proper Content-Disposition header for downloads

### File Size Limits
```
MAX_UPLOAD_SIZE = 5,368,709,120 bytes (5GB)
FILE_CHUNK_SIZE = 8,388,608 bytes (8MB per stream chunk)
UPLOAD_CHUNK_SIZE = 5,242,880 bytes (5MB per upload chunk)
```

---

## 🔐 Security Features

### Authentication & Authorization
```python
@login_required  # All endpoints require authentication
- Only authenticated users can access chat rooms
- Permission checks on room access
- Owner-only operations for group management
```

### Encryption
```python
# Message content encryption
encrypt_data(content)  # XOR encryption on save
decrypt_data(content)  # Decrypted when accessed

# Attachment filename encryption
attachment.file_name  # Encrypted in database
attachment.decrypted_file_name  # Property returns decrypted name
```

### File Access Control
```
1. URL tokens don't expose file paths
2. Files served through permission-checked view
3. Direct media serving disabled for attachments
4. Download logs maintained for audit
```

---

## 🔌 WebSocket Events

### Message Events
```javascript
// Send text message
{
    "type": "chat_message",
    "message": "Hello",
    "parent_id": null,
    "message_type": "text"
}

// Send file notification
{
    "type": "chat_message",
    "message": "Sent a file: document.pdf",
    "file_url": "/chat/api/download/123/",
    "file_name": "document.pdf",
    "file_type": "application/pdf",
    "message_type": "file"
}
```

### Status Events
```javascript
// Read receipt
{
    "type": "read_receipt"
}

// Typing indicator
{
    "type": "typing",
    "is_typing": true
}

// Presence update
{
    "type": "presence_change",
    "user_id": 1,
    "status": "online"
}
```

---

## 📊 Database Models

### ChatRoom
```python
- room_id: UUID (primary key)
- name: str (optional)
- room_type: 'direct' | 'group' | 'project'
- participants: ManyToMany[User]
- created_by: User
- created_at: DateTime
- updated_at: DateTime
```

### Message
```python
- id: int
- room: ForeignKey(ChatRoom)
- sender: ForeignKey(User)
- content: str (encrypted)
- message_type: 'text' | 'file' | 'voice' | 'task_link' | 'system'
- parent_message: ForeignKey(self, optional)
- is_edited: bool
- is_deleted: bool
- created_at: DateTime
- updated_at: DateTime
```

### ChatAttachment
```python
- id: int
- message: ForeignKey(Message)
- file: FileField (upload_to='chat_attachments/%Y/%m/%d/')
- file_name: str (encrypted)
- file_type: str (mime type)
- file_size: int (bytes)
- created_at: DateTime
```

### UserPresence
```python
- user: OneToOneField(User)
- is_online: bool
- last_seen: DateTime
```

### ReadReceipt
```python
- message: ForeignKey(Message)
- user: ForeignKey(User)
- read_at: DateTime
- unique_together: (message, user)
```

---

## 🛠️ API Endpoints

### Messages
```
GET  /chat/api/messages/<room_id>/          # Get message history
POST /chat/api/forward/                     # Forward message
POST /chat/api/bulk-delete/                 # Delete multiple messages
GET  /chat/api/search/                      # Search messages
POST /chat/api/clear/<room_id>/             # Clear chat history
```

### Files
```
POST /chat/api/upload/                      # Upload file(s)
GET  /chat/api/download/<attachment_id>/    # Download file (streaming)
POST /chat/api/upload-chunk/                # Upload chunk (for large files)
```

### Room Management
```
GET  /chat/api/quick-chat-list/             # Get all rooms + unread counts
POST /chat/create-group/                    # Create group
POST /chat/api/delete-group/<room_id>/      # Delete group (owner only)
POST /chat/api/leave-group/<room_id>/       # Leave group
POST /chat/api/add-member/<room_id>/<user_id>/
POST /chat/api/remove-member/<room_id>/<user_id>/
GET  /chat/api/non-members/<room_id>/
```

---

## 🐛 Troubleshooting Large Files

### Issue: File Upload Fails at 350MB
**Solution**: Chunked upload automatically engages for files > 500MB
- Frontend splits file into 5MB chunks
- Backend assembles and validates integrity
- Total limit is 5GB per file

### Issue: Download Times Out
**Solution**: Streaming response activated for files > 10MB
- Files sent in 8MB chunks
- Client can resume interrupted downloads
- Memory-efficient processing

### Issue: Permission Denied on Download
**Solution**: User must be participant in chat room
- Check room membership in admin panel
- Add user to room if needed
- Re-attempt download

### Issue: File Not Found After Upload
**Possible Causes**:
1. File storage path not writable
2. Database record not saved
3. Attachment record deleted with message
4. Media directory permissions issue

**Solution**:
```bash
# Check file storage
ls -la media/chat_attachments/

# Verify database
python manage.py dbshell
SELECT * FROM chat_chatattachment WHERE id=<attachment_id>;

# Check directory permissions
chmod 755 media/chat_attachments/
```

---

## 📈 Performance Optimization

### Database Queries
- **Prefetch relations** to avoid N+1 queries
- **Bulk operations** for message reads
- **Indexed fields** on room_id, sender_id, created_at

### File Storage
- **Organized by date**: `chat_attachments/YYYY/MM/DD/`
- **Unique filenames** to prevent conflicts
- **Automatic cleanup** via signals on deletion

### WebSocket Optimization
- **Channel layer groups** for efficient broadcasting
- **Async handlers** for non-blocking operations
- **Connection pooling** for database sync operations

### Frontend Optimization
- **Lazy load** message history
- **Virtual scrolling** for large message lists
- **Debounced** typing indicators
- **Optimistic UI** updates

---

## 🚀 Configuration

### Settings (core/settings.py)
```python
# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10737418240      # 10GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10737418240      # 10GB
DATA_UPLOAD_MAX_NUMBER_FILES = None             # Unlimited

# Media storage
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WebSocket configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

### Deployment Notes
- Use **Redis Channel Layer** for production (InMemory not suitable)
- Configure **S3 or Cloud Storage** for file handling
- Set up **proper nginx/gunicorn** for streaming
- Enable **CDN** for fast file delivery
- Use **HTTPS** for encrypted connections

---

## 📝 Recent Improvements

### Version 2.0 Changes
✅ **Streaming downloads** for files > 10MB
✅ **File size validation** on upload (5GB limit)
✅ **Permission-based** file access
✅ **Chunked upload** for large files
✅ **Secure URLs** instead of direct file paths
✅ **File integrity** verification
✅ **Memory-efficient** processing
✅ **Resume capability** on interrupted downloads
✅ **Better error** handling and logging

---

## 🔗 Related Documentation

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [WebSocket API Spec](https://tools.ietf.org/html/rfc6455)
- [File Upload Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [End-to-End Encryption](https://en.wikipedia.org/wiki/End-to-end_encryption)

---

## 📞 Support

For issues or questions about chat functionality:
1. Check error logs: `VSCODE_TARGET_SESSION_LOG`
2. Review database records in admin panel
3. Test with browser DevTools Network tab
4. Check Django logs for backend errors

**Last Updated**: 2026-06-24
**Version**: 2.0
**Status**: ✅ Production Ready
