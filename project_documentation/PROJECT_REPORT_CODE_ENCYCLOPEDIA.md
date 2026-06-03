# IIAP OM — Code & Logic Encyclopedia (Supplement)

> Companion to `PROJECT_REPORT_FULL.md`. Documents **every Python module**, **view function logic**, **services**, **signals**, and **integration flows** file-by-file.

---

## Table of Contents

1. [accounts](#1-accounts)
2. [tasks](#2-tasks)
3. [bugs](#3-bugs)
4. [testcases](#4-testcases)
5. [notes](#5-notes)
6. [files](#6-files)
7. [finance](#7-finance)
8. [events](#8-events)
9. [notifications](#9-notifications)
10. [chat](#10-chat)
11. [telescope](#11-telescope)
12. [inventory](#12-inventory)
13. [products](#13-products)
14. [stock](#14-stock)
15. [procurement](#15-procurement)
16. [audit (inventory)](#16-audit-inventory)
17. [reports (inventory)](#17-reports-inventory)
18. [dashboard (inventory)](#18-dashboard-inventory)
19. [core](#19-core)
20. [Cross-App Signal Map](#20-cross-app-signal-map)
21. [WebSocket Message Protocol](#21-websocket-message-protocol)

---

## 1. accounts

### 1.1 File inventory

| File | Purpose |
|------|---------|
| `models.py` | `User` model — roles, teams, PM/inventory/telescope flags |
| `forms.py` | `LoginForm`, `UserCreateForm`, `UserEditForm`, password forms |
| `middleware.py` | `InventoryAccessMiddleware` — session swap, path ACL |
| `urls.py` | All account routes |
| `views/auth_views.py` | Login/logout/password |
| `views/user_management_views.py` | PM + inventory + telescope user CRUD |
| `views/profile_views.py` | Profile and settings tabs |
| `admin.py` | Django admin with role badges |

### 1.2 `login_view` logic

```
IF user already authenticated → redirect tasks:dashboard
IF POST:
  IF form valid:
    user = form.get_user()
    IF NOT user.is_active → error "deactivated"
  IF NOT superuser AND NOT user.can_access_pm → error "Access Denied PM"
    login(request, user)
    DELETE session['inv_user_id']  # clear inventory session
    redirect next URL OR tasks:dashboard
  ELSE → error "Invalid username or password"
RENDER accounts/login.html
```

### 1.3 `inventory_login` logic

```
IF POST:
  TRY InventoryUser.get(username)
  IF check_password AND is_active:
    logout(request)  # clear PM session
    session['inv_user_id'] = user.id
    redirect /inventory/dashboard/
  ELSE error invalid credentials
```

### 1.4 `InventoryAccessMiddleware` — complete decision tree

```
ON each request:
  path = request.path
  is_pm_user = authenticated AND not AnonymousUser

  IF session['inv_user_id']:
    load InventoryUser
    IF NOT is_pm_user AND NOT path.startswith('/admin/'):
      request.user = inv_user

  IF path starts with /inventory/ OR /api/inventory/ (NOT /admin/):
    IF inv_user → request.user = inv_user
    ELIF pm_user AND can_access_inventory → OK
    ELSE → redirect accounts:login

    IF user NOT is_admin:
      FOR each protected prefix (adjustments, serials, limits, alerts, rentals, shortage):
        IF path matches prefix:
          IF NOT can_access_* → redirect /inventory/dashboard/
          IF POST AND NOT can_manage_* → redirect /inventory/dashboard/
      IF shortage export AND NOT can_manage_shortage_exports → redirect shortage page

  IF inv_user AND NOT pm_user:
    IF path NOT in allowed [/inventory/, /api/inventory/, /admin/, /accounts/, /media/, /static/]:
      redirect /inventory/dashboard/

  return get_response(request)
```

### 1.5 User model — permission properties

| Property | Returns True when |
|----------|-------------------|
| `is_admin` | `role == 'admin'` OR `is_superuser` |
| `is_project_manager` | `role == 'project_manager'` |
| `is_student` | `role == 'student'` |
| `display_name` | `nickname` OR full name OR username |
| `initials` | First letters of name parts (max 2) OR username[:2] |

---

## 2. tasks

### 2.1 File inventory (42 Python files)

| Path | Purpose |
|------|---------|
| `models.py` | All PM domain models + re-exports |
| `urls.py` | Master URLconf (~120 routes) |
| `signals.py` | Audit + auto module/project membership |
| `decorators.py` | `admin_required`, `manager_or_admin_required` |
| `context_processors.py` | Global template context |
| `calendar_sync.py` | Google + CalDAV sync |
| `apps.py` | Loads signals on ready |
| `views/dashboard_views.py` | Role-based dashboard |
| `views/project_views.py` | Project lifecycle |
| `views/task_views.py` | Task CRUD + status API |
| `views/module_views.py` | Modules + forum |
| `views/release_views.py` | Requirements, releases, RTM |
| `views/report_views.py` | Reports + master report |
| `views/misc_views.py` | Search, trash, restore |
| `views/audit_views.py` | PM audit log viewer |
| `services/project_service.py` | Folders, notifications, deletion |
| `services/release_service.py` | Snapshots, publish, ZIP |
| `services/notification_service.py` | Notification factory + WS |
| `services/report_engine.py` | MD/PDF/DOCX/XLSX generation |
| `api/endpoints.py` | AJAX JSON APIs |
| `utils/query_utils.py` | Visibility querysets |
| `forms/*.py` | Model forms |
| `templatetags/task_tags.py` | Template filters |

### 2.2 `Project.save()` — ID generation algorithm

```
IF project_id is empty:
  initials = first letter of each word in name (alpha only)
  IF no initials → random 3 uppercase letters
  year = current year
  count = projects created this year + 1
  LOOP:
    pid = f"PRJ-{initials}-{year}-{count:04d}"
    IF pid not exists → assign and break
    count += 1
super().save()
```

### 2.3 `Project.update_progress()` — full formula

```
tasks = all non-trash tasks
IF count == 0: progress = 0; SAVE; RETURN

FOR each task:
  weight = 0
  IF status == done: weight = 100
  ELIF status == review: weight = 80
  ELIF status == in_progress: weight = 30
  # blocked/todo = 0

  stats = task.test_case_stats
  IF stats.total > 0:
    weight = int(weight * 0.6 + stats.percentage * 0.4)

  total_progress += weight

progress = int(total_progress / task_count)
SAVE update_fields=['progress']
```

### 2.4 `Task.can_complete` — quality gate

```
test_cases = all linked TestCase rows
IF no test cases → return True
return count(status='passed') == count(all)
```

### 2.5 `task_update_status` — complete logic

```
LOAD task by pk
is_pm = user in task.project.managers
is_incharge = user == task.project.project_incharge
IF NOT (is_pm OR admin OR role PM OR is_incharge):
  return JSON 403

IF POST:
  PARSE JSON body → new_status
  IF new_status in STATUS_CHOICES:
    IF new_status == 'done' AND NOT task.can_complete:
      return JSON 400 "test cases must pass"
    old_status = task.status
    task.status = new_status
    task.save()  # triggers progress update

    IF moved to review/done from other AND task.release set:
      IF all release tasks in [review, done]:
        NOTIFY each project manager "Release ready"

    FOR each assignee NOT manager AND NOT self:
      NOTIFY task_updated

    return JSON {success, project.progress}
return JSON 400
```

### 2.6 `ProjectService.initialize_project_folders`

Creates this category tree on new project:

```
resources/
  notes/
  documents/
  assets/
requirements/
  specifications/
  test_management/
    test_cases/
    assessments/
releases/
+ README.md ProjectFile (is_public=True)
```

### 2.7 `ProjectService.handle_deletion_request`

| Action | Who | Effect |
|--------|-----|--------|
| `request_deletion` | Admin | Sets `deletion_requested_by_admin`; notifies all PMs |
| `request_deletion` | PM (must be manager) | Sets `deletion_requested_by_pm`; notifies all admins |
| `cancel_deletion` | Admin (if admin flag set) | Clears admin flag + timestamp |
| `cancel_deletion` | PM (if pm flag set) | Clears pm flag + timestamp |

**Full delete** (in `project_delete` view): requires BOTH flags true OR superuser force.

### 2.8 `ReleaseService` — release pipeline

| Method | Logic |
|--------|-------|
| `calculate_hash(file)` | SHA-256 over 4KB chunks |
| `create_release_snapshot(release, user, files?)` | IF locked → 0; IF snapshots exist → 0; FOR each latest ProjectFile: hash, copy to ReleaseFile, log |
| `publish_release` | snapshot → status=completed → published_at/by → sync to project Releases folder → ReleaseLog |
| `sync_release_to_project_resources` | Creates category `Releases/<release>/`, copies assets, builds ZIP bundle |

### 2.9 `get_visible_tasks_qs(user, qs)` — visibility rules

| User type | Sees tasks where |
|-----------|------------------|
| Admin | All non-trash |
| PM | Project manager OR member OR incharge |
| Member | `(is_approved OR created_by=self)` AND (manager OR assignee OR member OR incharge) |

### 2.10 View function catalog — `project_views.py`

| Function | Logic summary |
|----------|---------------|
| `project_list` | Filter by module/status/search; visibility by role |
| `project_create` | Form save → `initialize_project_folders` → notify assignments |
| `project_detail` | Tabs: overview, stats, recent tasks/files/bugs |
| `project_edit` | Manager/admin only |
| `project_settings` | Colors, visibility, dates |
| `project_members` | M2M managers/members/incharge |
| `project_delete` | Dual-flag deletion workflow |
| `project_archive_toggle` | Flip `is_archived` |
| `project_request_release` | Sets `release_requested` |
| `project_approve_release` | Admin approves → `is_released=True` |
| `project_task_list` | Kanban/list for project |
| `project_requirement_list` | Requirements table |
| `project_bug_list` | Bugs filtered to project |

### 2.11 View function catalog — `release_views.py` (selected)

| Function | Logic |
|----------|-------|
| `release_publish` | Calls `ReleaseService.publish_release` |
| `release_compare` | Diff two releases by file hash/name |
| `release_restore` | Restore files from release snapshot to project |
| `rtm_view` | Requirements Traceability Matrix HTML |
| `test_case_report` | Test summary per project/release |
| `requirement_approve` | Sets `is_approved=True` |

### 2.12 `tasks/signals.py` — all receivers

| Signal | Handler | Behavior |
|--------|---------|----------|
| `user_logged_in` | `log_user_login` | AuditLog with IP, user-agent |
| `user_logged_out` | `log_user_logout` | AuditLog logout |
| `post_save` Project/Requirement/Task/TestCase/Bug/Release | `audit_post_save` | create/update audit row |
| `post_delete` same models | `audit_post_delete` | delete audit row |
| `m2m_changed` Task.assignees | `add_task_assignees_to_module` | Auto ModuleMember + project.members |
| `post_save` Task | `add_task_module_members` | Same for assignees on save |

### 2.13 API endpoints (`tasks/api/endpoints.py`)

| Endpoint | GET params | Response |
|----------|------------|----------|
| `tasks_for_project` | `project_id` | `{tasks: [{id, title, task_id, requirement_id}]}` filtered by visibility |
| `project_modules_api` | `project_id` | `{modules: [{id,name}], is_manager}` |
| `project_requirements_api` | `project_id` | Approved non-trash requirements |
| `project_members_api` | `project_id` | Active members + managers `{id, name}` |

---

## 3. bugs

### 3.1 `bug_list` visibility

```
IF admin OR PM → all non-trash bugs
ELSE → bugs where user is manager OR incharge OR reporter OR assignee
APPLY filters: severity, status, project, assigned_to_me
```

### 3.2 `bug_create` side effects

```
SAVE bug with reported_by=request.user
FOR each project manager (not self):
  NOTIFY bug_reported
IF assignees exist:
  CREATE Task(title="[Bug] ...", task_type=bug, priority=severity)
  SET task.assignees = bug.assignees
  FOR each assignee: NOTIFY task_assigned
```

### 3.3 `bug_resolve` logic

```
ALLOW: admin, PM, incharge, OR assignee
IF status in [closed, wont_fix]: require admin/PM/incharge
SET resolution fields, resolved_by, resolution_date
IF linked_task: linked_task.status = 'done'; save
```

### 3.4 `bug_delete`

Soft delete: `is_in_trash=True`, `deleted_at`, `deleted_by`; also trashes linked task if exists.

---

## 4. testcases

### 4.1 `test_case_verify` workflow

```
ALLOW: admin, PM, OR user in assigned_members
UPDATE status, actual_result, attachments
CREATE TestCaseHistory row
IF status == passed: check all task TCs → if all pass NOTIFY PMs "ready for completion"
IF status == failed: NOTIFY assignees test_failed
IF status == retest: NOTIFY retest_requested
```

### 4.2 ID generation (`TestCase.save`)

```
prefix = project.project_id split or "PROJ"
count = test cases on project + 1
LOOP: tid = f"{prefix}-TC-{year}-{count:06d}" until unique
```

---

## 5. notes

### 5.1 `KnowledgeBaseNote.save()` sync logic

```
super().save()
IF project:
  GET_OR_CREATE FileCategory name="Notes"
  file_name = f"{title}.md"
  IF existing ProjectFile with same name in Notes cat:
    REPLACE file content bytes
  ELSE:
    CREATE new ProjectFile with ContentFile(markdown bytes)
```

### 5.2 `check_kb_access(note, user)` (in views)

```
RETURN True IF: author OR admin OR PM OR incharge
ELSE IF DocumentAccessRight with can_view
ELSE IF module member OR project member
ELSE False
```

---

## 6. files

### 6.1 `check_file_access(pf, user, access_type)` — authoritative rules

```
IF admin OR is_project_manager → True
IF uploaded_by == user → True
IF access_type in [edit, delete]:
  IF project manager OR member → True
  IF document/pdf/code AND uploaded_by → True
IF access_type != view → return False (after above)
IF pf.module (or task.module):
  RETURN ModuleMember exists
ELIF pf.project:
  RETURN user in project.members
RETURN False
```

### 6.2 `file_upload` versioning logic

```
FOR each uploaded file:
  FIND existing latest (same original_name, category, project, versions__isnull=True)
  IF exists:
    CREATE new ProjectFile with parent_file=existing, version=existing.version+1
    existing becomes parent chain head shift
  ELSE:
    CREATE version=1
  DETECT file_type from extension
  SAVE with upload_to() path
```

### 6.3 `file_delete` — dual approval

```
Soft delete → is_in_trash=True
IF admin requests deletion → admin_approved_deletion=True
IF PM requests → pm_approved_deletion=True
Permanent delete only when BOTH approvals OR admin force
```

### 6.4 `document_discussion` / `folder_discussion`

- Loads PDF or folder context
- `FileComment` with optional `annotation_coords` for PDF markup
- POST adds comment; supports reply threading via `parent`
- Embeds annotations into PDF via `embed_pdf_annotations()` (PyPDF manipulation)

### 6.5 View catalog

| View | File | Key logic |
|------|------|-----------|
| `file_list` | file_list_views | Global search, filters, repo category tree |
| `project_files` | file_list_views | Per-project browser |
| `file_upload` | upload_views | Multi-file + versioning |
| `file_download/view` | serve_views | Access check + serve |
| `download_folder` | serve_views | ZIP all latest files in category |
| `move_item` | manage_views | Move file/category in tree |
| `file_audit_logs` | manage_views | File-specific audit listing |

---

## 7. finance

### 7.1 `project_expenses`

```
REQUIRE: project member OR manager OR admin
LIST expenses ordered by -date_incurred
SHOW budget.remaining_budget
```

### 7.2 `expense_create` / `budget_edit`

```
@manager_or_admin_required  # global PM role or admin, NOT per-project only
SAVE Expense with logged_by=request.user
Optional receipt FK → ProjectFile
```

---

## 8. events

### 8.1 `calendar_view`

```
BUILD events list:
  - User's created events + attended events
  - Task due_date/deadline overlays as pseudo-events
SERIALIZE for FullCalendar JSON
```

### 8.2 Google OAuth flow

```
google_calendar_init (admin only):
  Build OAuth flow → redirect Google
google_calendar_callback:
  Exchange code → store token JSON on UserCalendarSettings
  is_google_synced = True
```

### 8.3 Event save side effect

On create/update → `calendar_sync.sync_event_to_external()` for creator's settings.

---

## 9. notifications

### 9.1 `notifications_list`

```
FILTER recipient=request.user
OPTIONAL: status, type, project, sender, timeframe, search
SUPPORT ?mark_all → mark all read
```

### 9.2 `notification_read`

```
MARK is_read=True
REDIRECT based on FK:
  - task → task_detail
  - project → project_detail
  - chat type → chat home with room
```

### 9.3 `NotificationService.create_notification`

```
IF recipient == sender: SKIP
CREATE Notification row
TRY channel_layer.group_send("user_{id}", {type: new_notification, unread_count, notification})
EXCEPT: pass silently
```

---

## 10. chat

### 10.1 `ChatConsumer.receive` message types

| type | Action |
|------|--------|
| `chat_message` | save_message → broadcast to room → notify other participants via `user_{id}` |
| `read_receipt` | mark_messages_as_read → broadcast messages_read |
| `edit_message` | update if within 10 min and sender match |
| `delete_message` | soft delete is_deleted=True |
| `add_reaction` | MessageReaction get_or_create |
| `typing` | broadcast user_typing |

### 10.2 DM room normalization

```
IF room_name starts with "DM-":
  participant_id = split[1]
  normalized = f"DM-{min(user.id, participant_id)}-{max(...)}"
  get_or_create ChatRoom(name=normalized, room_type=direct)
  ADD both users to participants
```

### 10.3 `chat/signals.py`

| Signal | Action |
|--------|--------|
| `post_save User` | Create `UserPresence` |
| `post_save Project` | Create project ChatRoom; add creator + managers |
| `m2m_changed Project.members` | Add new members to project chat room |

### 10.4 HTTP API routes

| Route | Method | Logic |
|-------|--------|-------|
| `api/messages/<room_id>/` | GET | Paginated messages respecting ChatClear |
| `api/upload/` | POST | Save ChatAttachment + Message |
| `api/clear/<room_id>/` | POST | Set ChatClear timestamp for user |
| `api/forward/` | POST | Copy message to target room |
| `api/bulk-delete/` | POST | Soft-delete multiple messages |

### 10.5 `ai_utils.py` (optional)

Uses `GEMINI_API_KEY` for chat summarization and task extraction from conversation.

---

## 11. telescope

### 11.1 `ensure_default_telescopes()`

If DB empty, seeds: VBT, JCBT, Zeiss, 75cm Cassegrain, 45cm Schmidt with default metadata.

### 11.2 Access matrix

| Action | Required |
|--------|----------|
| View dashboard/detail | `can_access_telescope` OR superuser |
| Create/edit/delete | `is_telescope_admin` OR superuser |

---

## 12. inventory

### 12.1 `recalculate_branch_stock(product, branch)`

```
stock_in = SUM(StockEntry WHERE type=in)
stock_out = SUM(StockEntry WHERE type=out)
adjustments = SUM(InventoryAdjustment.quantity)  # signed
current_quantity = max(0, stock_in + adjustments - stock_out)
SAVE BranchStock
```

### 12.2 Signal receivers (`inventory/signals.py`)

| Event | Trigger |
|-------|---------|
| StockEntry pre_save | Store old branch/product |
| StockEntry post_save/delete | Recalculate current + old branch if changed |
| InventoryAdjustment pre_save/post_save/delete | Same |

### 12.3 Adjustment page logic

```
POST adjustment:
  IF decrease → quantity = -abs(qty)
  CREATE InventoryAdjustment
  AuditLog.log()
  IF not admin → notify_inventory_admins()
```

### 12.4 Rental workflow

```
CREATE rental:
  VALIDATE quantity <= BranchStock.current_quantity
  CREATE StockEntry type=out
  SAVE rental active

RETURN rental:
  CREATE StockEntry type=in
  SET rental returned timestamp
```

### 12.5 Management commands

| Command | Purpose |
|---------|---------|
| `check_alerts` | Scan BranchStock vs limits → create/resolve Alert rows |
| `recalculate_stock` | Bulk recalc all BranchStock |
| `sync_serials` | CLI serial sync |

---

## 13. products

### 13.1 Bulk Excel import columns

**Required:** Name, SKU, Price  
**Optional:** Category, Brand, Description, Quantity, Rack, Shelf  
**Behavior:** Skip duplicates; create BranchStock when branch resolved.

### 13.2 `ProductListPageView`

Lists via `BranchStock` join (not Product directly) for accurate per-branch quantities.

---

## 14. stock

### 14.1 `StockOutPageView` validation

```
IF quantity > BranchStock.current_quantity:
  REJECT with error message
ELSE:
  CREATE StockEntry out
  (signal recalculates stock)
```

### 14.2 `StockTransfer` lifecycle

```
CREATE transfer (pending):
  IMMEDIATE StockEntry OUT at from_branch

RECEIVE (to_branch staff or super_admin):
  StockEntry IN at to_branch
  UPDATE rack/shelf/local_sku on BranchStock
  status = received
```

---

## 15. procurement

### 15.1 Approve flow (admin only)

```
status = approved
CREATE StockEntry IN for fulfilled_quantity at branch
NOTIFY requester
AuditLog.log()
```

### 15.2 Insufficient stock heuristic

`current_stock < 10` flags insufficient (independent of QuantityLimit).

---

## 16. audit (inventory)

### 16.1 `AuditLog.log(user, action, instance, changes)`

```
branch = user.branch OR instance.branch
model_name = instance.class name OR "System"
object_id = instance.pk OR 0
CREATE AuditLog row
```

### 16.2 Export limits

PDF export capped at 200 rows.

---

## 17. reports (inventory)

### 17.1 `StatisticsReportView` aggregates

- Product counts, stock in/out totals, rental stats, adjustment sums
- 12-month chart data
- Merged recent transaction feed
- All querysets filtered by `get_isolated_products` / `filter_by_branch`

---

## 18. dashboard (inventory)

### 18.1 Role routing

```
IF super_admin → redirect superadmin dashboard
IF branch_admin → redirect branch dashboard
ELSE staff → show KPI dashboard (products, stock sum, turnover, shrinkage, alerts)
```

### 18.2 KPI formulas (staff)

```
turnover = total_stock_out / average_inventory
shrinkage = negative_adjustments / stock_in  # note: adjustment types are manual/automated in model
```

---

## 19. core

### 19.1 `core/asgi.py`

```python
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(URLRouter(chat.routing.websocket_urlpatterns)),
})
```

### 19.2 WebSocket routes (`chat/routing.py`)

| Path | Consumer |
|------|----------|
| `ws/chat/<room_id>/` | `ChatConsumer` |
| `ws/notifications/` | `NotificationConsumer` |

---

## 20. Cross-App Signal Map

```
Project created
  ├─ chat.signals → ChatRoom (project type)
  ├─ project_views → ProjectService.initialize_project_folders
  └─ (optional) notifications

Task assignees added (m2m)
  ├─ tasks.signals → ModuleMember + project.members
  └─ views may → NotificationService

Task saved
  ├─ tasks.signals → audit + module members
  └─ Task.save → Project.update_progress()

StockEntry saved
  └─ inventory.signals → recalculate_branch_stock()

KnowledgeBaseNote saved
  └─ notes.models.save → ProjectFile sync

Bug assignees on create
  └─ bugs.views → Task creation + notifications
```

---

## 21. WebSocket Message Protocol

### Client → Server (JSON)

```json
{"type": "chat_message", "message": "text", "parent_id": null, "message_type": "text"}
{"type": "read_receipt"}
{"type": "edit_message", "message_id": 1, "message": "edited"}
{"type": "delete_message", "message_id": 1}
{"type": "add_reaction", "message_id": 1, "emoji": "👍"}
{"type": "typing", "is_typing": true}
```

### Server → Client (JSON)

```json
{"type": "chat_message", "id": 1, "message": "...", "sender": "user", "timestamp": "14:30", ...}
{"type": "messages_read", "user": "user", "reader_id": 1}
{"type": "message_edited", "message_id": 1, "message": "..."}
{"type": "message_deleted", "message_id": 1}
{"type": "presence_change", "user_id": 1, "status": "online"}
{"type": "typing", "user": "user", "is_typing": true}
```

---

## Known Implementation Quirks

| # | Issue | Location |
|---|-------|----------|
| 1 | `notify_inventory_admins` filters `role="admin"` but roles are `super_admin/branch_admin/staff` | `inventory/notifications.py` |
| 2 | Adjustment UI uses increase/decrease; model choices are manual/automated | `inventory/views/adjustment_views.py` |
| 3 | `bugs/urls.py` not mounted at root — use `tasks:bug_*` names | `core/urls.py` |
| 4 | Audit post_save may log `user=None` on updates | `tasks/signals.py` |
| 5 | InMemory channel layer — not multi-process safe | `core/settings.py` |
| 6 | `SECRET_KEY` and `DEBUG=True` in committed settings | `core/settings.py` |

---

## 22. Trash & Restore System (`misc_views.py`)

### 22.1 `trash_view` — unified recycle bin

```
LOAD filters: q, project, deleted_by, days
DEFINE filter_qs(qs):
  IF project_id → filter project_id
  IF deleted_by → filter deleted_by_id
  IF days → deleted_at >= now - timedelta(days)
  IF search → icontains on title/name/original_name + description

IF admin OR PM:
  tasks, requirements, files, notes, test_cases, bugs, categories = ALL is_in_trash=True (filtered)
  deleters = all Users who have any deleted_* relations
ELSE:
  SAME models BUT deleted_by=request.user ONLY
  deleters = empty
  projects = only projects user is involved in

RENDER tasks/trash.html with 7 entity lists
```

### 22.2 Restore authorization pattern

| Entity | Who can restore |
|--------|-----------------|
| Task | admin, project manager/incharge, OR created_by |
| Requirement | admin, manager/incharge |
| TestCase | admin, manager/incharge |
| Bug | admin, manager/incharge, reporter |
| File/Category | admin, manager, uploader |
| Note | admin, author, manager |

`permanent_delete` views: typically admin or dual-approval only; removes DB row and physical file.

---

## 23. Dashboard Logic (`dashboard_views.py`)

### 23.1 Admin dashboard

```
stats = {
  total_projects, active_projects (not completed/cancelled),
  total_users, db_size_mb from sqlite file size,
  deletion_reqs: projects with ONE deletion flag set but not both
}
RENDER admin_dashboard.html with top 6 projects by updated_at
```

### 23.2 PM / Member dashboard

```
projects = filtered by role (PM: manager|member|incharge; member: members only)
visible_tasks = get_visible_tasks_qs(...)
my_open_tasks = assigned to user, not done
overdue_tasks = due_date < today
due_today = due_date == today
my_open_bugs_count = assigned bugs not closed
notifications = last 5 unread
RENDER tasks/dashboard.html
```

---

## 24. Inventory Decorators (`inventory/decorators.py`)

| Decorator | Pass condition | Redirect on fail |
|-----------|----------------|------------------|
| `super_admin_required` | `user.is_super_admin` | dashboard-page |
| `branch_admin_required` | `user.is_branch_admin` | dashboard-page |
| `staff_permission_required('can_add_inventory')` | super_admin OR branch_admin OR getattr(perm) | dashboard-page |

Works with both `InventoryUser` and PM `User` when middleware sets request.user.

---

## 25. `Release` Model — Full Field Logic

| Field | Behavior |
|-------|----------|
| `release_type` | partial = minor/nightly; phase = major |
| `status` | planning → active → completed |
| `is_locked` | property: True when status==completed |
| `is_approved` | Gate before certain operations |
| `is_draft` / `is_prerelease` | GitHub-style release flags |
| `checksum` | Bundle-level hash after publish |
| `metadata` | JSON extensibility |
| `unique_together` | (project, name) |

**Validation on save:** If existing row was locked → raise ValidationError.

---

## 26. `ProjectFile` — Complete Property & Save Logic

| Property/Method | Logic |
|-----------------|-------|
| `detect_file_type(ext)` | Static: maps extension set → FILE_TYPE_CHOICES |
| `full_path` | project name + category ancestors + filename |
| `is_previewable` | image/pdf/text types |
| `save()` | Updates file path on disk if category renamed; increments counters |
| `get_project_relative_path()` | Used by release snapshots |

**Trash fields:** `is_in_trash`, `hidden_from_user_trash`, `admin_approved_deletion`, `pm_approved_deletion`.

---

## 27. `DocumentAccessRight` — KB & File ACL

| Field | Meaning |
|-------|---------|
| `user` | Target user |
| `project_file` OR `kb_note` | One of two FKs |
| `can_view` / `can_edit` / `can_delete` | Granular flags |

Used by `notes.views.check_kb_access` and file access overrides.

---

## 28. `calendar_sync.py` — External Sync Logic

```
sync_event_to_external(event, user_settings):
  IF is_google_synced AND token valid:
    create/update Google Calendar event via API
  IF is_caldav_synced:
    PUT to Radicale CalDAV path stored on event.caldav_event_path

On event delete:
  Remove from Google + CalDAV if IDs exist
```

Fallback: uses first admin's calendar settings if creator has none.

---

## 29. `report_engine.py` — Master Report Sections

Generated for `master_report` view (formats: md, pdf, docx, xlsx):

1. Project overview (metadata, progress, dates)
2. Requirements table (all statuses)
3. Tasks summary (by status, assignee)
4. Test case matrix (pass/fail/pending)
5. Bug report summary
6. Release history
7. Team members list
8. File inventory (latest versions)

Uses project ORM aggregations + template strings; xlsx via XlsxWriter; pdf via xhtml2pdf.

---

## 30. `global_search` (`misc_views.py`)

```
QUERY param q (min length threshold in view)
SEARCH across (role-filtered):
  - Projects (name, project_id, description)
  - Tasks (title, task_id, description)
  - Requirements (name, req_id)
  - ProjectFiles (original_name, title)
  - KnowledgeBaseNote (title, content)
  - BugReport (title)
RETURN grouped results template search/search_results.html
```

---

## 31. Complete Python File Count by App

| App | .py files (excl. migrations) | Primary responsibility |
|-----|------------------------------|----------------------|
| accounts | 8 | Auth, users, middleware |
| tasks | 25+ | PM core |
| bugs | 5 | Defects |
| testcases | 5 | QA |
| notes | 6 | KB |
| files | 12 | Documents |
| finance | 5 | Budget |
| events | 5 | Calendar |
| notifications | 4 | Alerts |
| chat | 8 | Messaging |
| telescope | 5 | Observatory |
| inventory | 20+ | Stock core |
| products | 10 | Catalog |
| stock | 8 | Movements |
| procurement | 5 | Purchasing |
| audit | 4 | Inv. audit |
| reports | 5 | Analytics |
| dashboard | 3 | Inv. home |
| core | 4 | Config |

**Total custom Python modules:** ~130+ (excluding migrations, venv).

---

*End of Code Encyclopedia*
