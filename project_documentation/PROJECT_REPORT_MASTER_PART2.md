# IIAP OM — Master Technical Report (Part 2 of 3)

# CHAPTER VI — BUG TRACKING (`bugs`)

## VI.1 Narrative Overview

The bugs application provides a **formal defect repository** separate from generic `task_type='bug'` tasks yet tightly coupled to them. When assignees are designated at creation time, the system automatically spawns a linked **Task** so bug work appears on kanban boards and release cut-down reports. Database tables retain legacy names `tasks_bugreport` and `tasks_bugcomment` after the app extraction—migrations preserve production data.

## VI.2 Severity & Status Lifecycles

**Severity** (low → critical) drives prioritization filters and may copy to linked task priority. **Status** flows: open → in_progress → resolved → closed, with **wont_fix** as terminal alternative. Resolution captures `resolution_summary`, `solving_results`, optional `resolution_attachment`, `resolved_by`, and `resolution_date` for audit defensibility.

## VI.3 Visibility Model (Paragraph)

Administrators and project managers observe all non-trashed bugs institute-wide. Regular members see bugs only when they are reporters, assignees, project managers, or project incharge for the bug’s project. This prevents cross-project leakage in multi-team installations. The list view supports filters: severity, status, project, “assigned to me”.

## VI.4 Creation Side Effects (Detailed Flow)

```
User submits BugReportForm
        │
        ▼
bug.reported_by = current user; SAVE
        │
        ├──► Notify each project manager (type: bug_reported)
        │
        └──► IF assignees not empty:
                 CREATE Task(title="[Bug] …", task_type=bug)
                 COPY assignees to task.assignees
                 NOTIFY each assignee (type: task_assigned)
```

**Paragraph:** The dual-record pattern (BugReport + Task) exists because stakeholders think in two vocabularies: quality teams track bugs; delivery teams track tasks. Linking via `linked_task` FK allows resolution to close both records simultaneously in `bug_resolve`.

## VI.5 Resolution & Closure Authority

Assignees may resolve bugs to **resolved** status. Transition to **closed** or **wont_fix** requires elevated authority (admin, PM, or incharge)—preventing premature closure without oversight. On resolve, linked tasks jump to `done`, synchronizing dashboards.

## VI.6 Threaded Comments

`BugComment` supports `parent` for threading and file attachments under `media/bugs/comments/`. The detail page posts via `bug_comment_add` without full page reload in some templates.

## VI.7 Soft Delete

`bug_delete` sets `is_in_trash`, timestamps, and `deleted_by`. Linked tasks may also trash. Restore/permanent-delete routes live in `misc_views` under `tasks:` namespace.

---

# CHAPTER VII — TEST CASE MANAGEMENT (`testcases`)

## VII.1 Narrative Overview

Test cases embody **verification discipline**. Each case belongs to exactly one **project** and one **task**, tying QA activity to deliverables. The platform enforces that a task cannot reach **done** until every linked test case reports status **passed**—a rare but powerful gate in open-source PM tools.

## VII.2 Test Case Anatomy

Fields include `scenario`, `preconditions`, `steps`, `expected_result`, `actual_result`, `priority`, `status`, `approval_status`, and M2M `assigned_members`. Attachments store evidence (screenshots, logs). `TestCaseHistory` append-only rows record verify actions for compliance.

## VII.3 ID Generation

IDs follow `{PROJECT_PREFIX}-TC-{YEAR}-{######}` ensuring sortable uniqueness per project year. Collision handling loops incrementing sequence—same pattern as tasks and requirements.

## VII.4 Verification Workflow (Full)

```
┌──────────┐     assign      ┌─────────────┐
│  pending │ ───────────────►│  tester     │
└────┬─────┘                 │  executes   │
     │                       └──────┬──────┘
     │                              │
     │         ┌────────────────────┼────────────────────┐
     │         ▼                    ▼                    ▼
     │    ┌─────────┐         ┌─────────┐         ┌─────────┐
     │    │ passed  │         │ failed  │         │ retest  │
     │    └────┬────┘         └────┬────┘         └────┬────┘
     │         │                   │                   │
     │         ▼                   ▼                   ▼
     │   Notify PMs          Notify assignees    Notify retest
     │   "ready to close"    test_failed         requested
     │   if ALL TCs pass
     ▼
┌─────────┐
│ blocked │ (environment / dependency)
└─────────┘
```

**Paragraph:** The verify view (`test_case_verify`) accepts status updates, actual results, and attachments in one POST. When the last failing test turns passed, notification logic scans the parent task’s full test case set—only then PMs receive “task ready for completion” alerts.

## VII.5 Permissions

Create/edit/delete: admin, global PM role, or **project incharge/manager** for that project. Verify: additionally assigned members may record results—distributing QA load.

## VII.6 Bulk Import

`test_case_bulk_create` accepts tabular input for migration from Excel-based test repositories—common when institutes adopt IIAP OM mid-project.

---

# CHAPTER VIII — KNOWLEDGE BASE (`notes`)

## VIII.1 Narrative Overview

Knowledge base notes are **Markdown documents** optionally scoped to projects and modules. Uniquely, the platform **mirrors** every save into the files subsystem as `Notes/{title}.md` under the project—unifying search, permissions, and release snapshots with binary uploads.

## VIII.2 Access Control Layers

Access checks cascade: author, admin, PM, incharge → explicit `DocumentAccessRight` rows → module membership → project membership. Global notes (`project=NULL`) remain visible only to author unless admin—supporting personal drafts.

## VIII.3 Synchronization Logic (Paragraph)

On `KnowledgeBaseNote.save()`, the ORM ensures a `FileCategory` named “Notes” exists, then either updates an existing `ProjectFile` with matching `original_name` or creates a new file with UTF-8 encoded bytes. Engineers editing through the KB UI therefore need not manually upload `.md` files—the filesystem mirror stays consistent for release engineers using folder ZIP exports.

## VIII.4 Trash & Restore

Notes participate in unified trash with `deleted_by` tracking. Permanent delete removes KB row; associated `ProjectFile` may require separate trash handling depending on delete view implementation.

---

# CHAPTER IX — FILE & DOCUMENT MANAGEMENT (`files`)

## IX.1 Narrative Overview

The files application is a **document management system (DMS)** embedded in PM. It provides hierarchical categories, versioning, inline preview, PDF annotation discussions, folder-level threads, per-user ACLs, dual-approval permanent deletion, and integration with finance (receipts) and releases (snapshots).

## IX.2 Storage Layout Philosophy

Physical paths mirror logical structure: `media/projects/{PRJ-ID}/{category path}/[vN/]{filename}`. This enables IT staff to browse the filesystem directly during backups. Notes land in `media/resources/notes/` when category is “Notes”.

## IX.3 Versioning Deep Dive

When uploading a file whose `original_name` already exists in the same project/category:

1. A new `ProjectFile` row is created with `version = old.version + 1`.
2. `parent_file` points to the previous head.
3. List views query `versions__isnull=True` to show only tips of version chains.
4. Historical versions remain downloadable for audit.

```
  v1 (parent_file=NULL) ◄── v2 (parent=v1) ◄── v3 (parent=v2)  ← "latest"
```

## IX.4 Access Control Function

`check_file_access(pf, user, access_type)` is the single authority:

- Admins and PM role bypass checks.
- Uploaders always access their files.
- **Edit/delete** grants project managers/members additional rights; code files restrict edit to uploader.
- **View** grants module members via `ModuleMember` table, else project members.

Failures return HTTP 403 on download/view routes.

## IX.5 Document Discussion & PDF Annotations

`document_discussion` renders PDFs with comment overlays. `FileComment.annotation_coords` stores JSON coordinate lists; `embed_pdf_annotations()` merges comments into downloadable PDFs for external reviewers—supporting optics/engineering drawing review workflows.

`folder_discussion` applies the same threading model to `FileCategory` nodes—discussing a specification folder without picking a single file.

## IX.6 Move, ZIP, Manage

`move_item` relocates files or subtrees between categories with validation against circular parents. `download_folder` streams ZIP of latest files in category subtree. `manage_resource` handles bulk operations from admin UI.

## IX.7 Deletion Governance

Soft delete moves items to trash. **Permanent delete** may require both `admin_approved_deletion` and `pm_approved_deletion` on sensitive projects—preventing single-actor data loss.

## IX.8 System Settings

`files.SystemSettings.max_file_size_gb` caps uploads (default 10 GB)—aligned with Django `DATA_UPLOAD_MAX_MEMORY_SIZE`.

---

# CHAPTER X — FINANCE (`finance`)

## X.1 Narrative Overview

Finance tracking stays intentionally lightweight: **one budget per project** and unlimited **expense line items** with categories (hardware, software, travel, services, materials, other). Receipts may reference existing `ProjectFile` rows—linking paper trail to document management.

## X.2 Budget Mathematics

`Budget.remaining_budget = total_amount - sum(expense.amount)`. No currency conversion is modeled; all amounts are decimal rupees/dollars per institute convention.

## X.3 Permission Model

Viewing expenses: project members/managers. Creating expenses and editing budgets: `@manager_or_admin_required`—meaning institute PM role or admin, not merely project manager on one project. Institutes wanting per-project manager finance control would adjust this decorator.

## X.4 User Journey

```
PM opens /finance/project/42/
    → sees table of expenses + budget bar
    → clicks Add Expense
    → fills amount, category, date, optional receipt file link
    → redirects back with updated remaining budget
```

---

# CHAPTER XI — CALENDAR & EVENTS (`events`)

## XI.1 Narrative Overview

The calendar integrates **internal events** with optional **Google Calendar** OAuth and **CalDAV** (Radicale) sync. Task due dates and deadlines overlay as read-only calendar entries—giving managers a single pane for meetings and delivery dates.

## XI.2 Event Model

`CalendarEvent` types: milestone, meeting, deadline, review, other. Fields include `meeting_link`, `meeting_password`, `location`, color hex, and external IDs (`google_event_id`, `caldav_event_path`). M2M `attendees` drives notification fan-out on create.

## XI.3 Google OAuth (Admin-Only Init)

Only administrators initiate org-wide Google OAuth (`google_calendar_init`). Tokens store as JSON on `UserCalendarSettings`. Callback view exchanges code, sets `is_google_synced`. This prevents members from granting rogue API access.

## XI.4 Sync Engine (`calendar_sync.py`)

On save/delete, events push to Google Calendar API or CalDAV PUT/DELETE. If creator lacks settings, sync may fall back to first admin’s configuration—documented behavior for small teams.

## XI.5 FullCalendar UI

`calendar_view` serializes events as JSON for FullCalendar.js with filters. CRUD views enforce edit rights: creator or admin/PM.

---

# CHAPTER XII — NOTIFICATIONS (`notifications`)

## XII.1 Narrative Overview

Notifications are **in-app rows** plus optional **WebSocket pushes** to connected browsers. They do not replace email—though `email_notifications` on User exists for future SMTP integration.

## XII.2 Type Catalog & Triggers

| Type | Typical trigger |
|------|-----------------|
| task_assigned | Assignee M2M change |
| task_updated | Status change by manager |
| task_completed | Status → done |
| comment_added | Task comment POST |
| due_soon / overdue | Cron/management (if enabled) |
| project_update | Membership, deletion request, release ready |
| test_* | Verify pass/fail/retest |
| chat_message | DM received |
| bug_reported | New bug on project |

## XII.3 Notification Center UX

`/notifications/` supports filters: read/unread, type, project, sender, timeframe, full-text search. `?mark_all` bulk-reads. Click-through (`notification_read`) routes to task, project, or chat deep link.

## XII.4 Real-Time Channel

`NotificationService` uses Channels group `user_{recipient_id}` with event type `new_notification` carrying unread count and payload snippet—navbar badge updates without refresh.

---

# CHAPTER XIII — REAL-TIME CHAT (`chat`)

## XIII.1 Narrative Overview

Chat delivers **WhatsApp-class** messaging inside the institute VPN. Three room types exist: **direct** (normalized DM ids), **group** (user-created), and **project** (auto-provisioned). Messages support text, files, voice notes, task links, and system messages.

## XIII.2 WebSocket Architecture

```
Browser                    Daphne / Channels
   │                              │
   │──── ws/chat/{room_id}/ ─────►│ ChatConsumer.connect()
   │                              │  - auth check
   │                              │  - join group chat_{uuid}
   │                              │  - presence group
   │◄─── chat_message ────────────│ group_send
   │──── chat_message JSON ───────►│ save Message → broadcast
```

## XIII.3 Message Operations

| Client event | Server behavior |
|--------------|-----------------|
| chat_message | Persist Message; broadcast; notify offline users |
| read_receipt | Mark ReadReceipt rows; broadcast messages_read |
| edit_message | Allowed 10 minutes for sender only |
| delete_message | Soft delete `is_deleted` |
| add_reaction | MessageReaction unique triple |
| typing | Ephemeral broadcast |

## XIII.4 Per-User Clear

`ChatClear` stores timestamp per (user, room). History API hides messages before clear—privacy without deleting others’ copies.

## XIII.5 HTTP APIs

REST-style endpoints under `/chat/api/` support mobile clients or fallback when WebSockets blocked: fetch messages, upload files, search, forward, bulk delete.

## XIII.6 AI Utilities (Optional)

`ai_utils.py` calls Gemini API for summarization—requires `GEMINI_API_KEY` environment variable; failure is non-fatal.

## XIII.7 Project Room Lifecycle

Creating a project auto-creates chat room; adding members via M2M adds them to room participants—ensuring new hires see project channel immediately.

---

# CHAPTER XIV — TELESCOPE OPERATIONS (`telescope`)

## XIV.1 Narrative Overview

The telescope module presents a **mission control style dashboard** for VBO observatory assets. It is read-heavy: status fields (observing/idle/maintenance), target name, RA/Dec, dome state, CCD temperature, tracking enabled/disabled. Image fields support upload or external `image_url`.

## XIV.2 Default Instrument Seed

If database empty on dashboard load, `ensure_default_telescopes()` inserts five canonical instruments—reducing blank-state onboarding for demos.

## XIV.3 Permission Matrix (Extended)

| Action | Requirement |
|--------|-------------|
| View dashboard | `can_access_telescope` or superuser |
| View detail | Same |
| Create/edit/delete | `is_telescope_admin` or superuser |
| Operate controls (future) | Per-instrument flags on User |

## XIV.4 Separation from PM Login

`telescope_login` requires telescope flag but denies PM dashboard—operators without `can_access_pm` still authenticate. User management tab in accounts provisions these identities.

## XIV.5 Data Model Narrative

Each `Telescope` row uses `id_name` slug (e.g. `vbt_234`) unique across inventory. `history` and `description` text fields hold long-form content from observatory documentation—rendered on detail template.

---

*End of Part 2 — Continue with Part 3 for Inventory, Security, Deployment, Glossary*
