# IIAP OM — Integrated Institute Management Platform

## Complete End-to-End Project Report Document

---

| Document Property | Value |
|-------------------|-------|
| **Project Title** | IIAP OM (IIA Project Management & Operations Platform) |
| **Document Version** | 2.0 (Reference) — **3.0 Master (~100 pages)** available |
| **Master Report** | `PROJECT_REPORT_MASTER_INDEX.md` → Parts 1–3 + this file + encyclopedia |
| **Companion Doc** | `PROJECT_REPORT_CODE_ENCYCLOPEDIA.md` (per-file logic) |
| **Software Version** | 2.0 (Multi-Module Enterprise Build) |
| **Document Date** | May 29, 2026 |
| **Author / Maintainer** | Engineering Team — IIA Management |
| **Classification** | Internal Technical Documentation |
| **Primary Language** | Python 3.10+ |
| **Framework** | Django 4.2 |
| **Database (Current)** | SQLite (`db.sqlite3`) |
| **Database (Production Target)** | PostgreSQL |
| **Timezone** | Asia/Kolkata |
| **Repository Root** | `IIA Management/` |

---

## Table of Contents

1. [Front Matter & Overview](#1-front-matter--overview)
2. [Module-by-Module Breakdown](#2-module-by-module-breakdown)
   - 2.1 [Core Configuration](#21-core-configuration-core)
   - 2.2 [Accounts & Authentication](#22-accounts--authentication-accounts)
   - 2.3 [Tasks — PM Core](#23-tasks--project-management-core-tasks)
   - 2.4 [Bugs](#24-bugs-bugs)
   - 2.5 [Test Cases](#25-test-cases-testcases)
   - 2.6 [Notes / Knowledge Base](#26-notes--knowledge-base-notes)
   - 2.7 [Files & Document Management](#27-files--document-management-files)
   - 2.8 [Finance](#28-finance-finance)
   - 2.9 [Events & Calendar](#29-events--calendar-events)
   - 2.10 [Notifications](#210-notifications-notifications)
   - 2.11 [Chat & Real-Time Messaging](#211-chat--real-time-messaging-chat)
   - 2.12 [Telescope Operations](#212-telescope-operations-telescope)
   - 2.13 [Inventory Subsystem](#213-inventory-subsystem)
   - 2.14 [Media Storage Layer](#214-media-storage-layer)
   - 2.15 [Dual Audit Systems](#215-dual-audit-systems)
3. [System Design & Visual Architecture](#3-system-design--visual-architecture)
4. [Technical Implementation & Security](#4-technical-implementation--security)
5. [Testing & Deployment](#5-testing--deployment)
6. [Appendices](#6-appendices)
7. [Complete URL Route Encyclopedia](#7-complete-url-route-encyclopedia)
8. [Forms & Validation Reference](#8-forms--validation-reference)
9. [Templates & Static Assets Inventory](#9-templates--static-assets-inventory)
10. [Business Logic Flowcharts (All Modules)](#10-business-logic-flowcharts-all-modules)
11. [Services, Signals & Background Jobs](#11-services-signals--background-jobs)
12. [Model Field Reference (All Tables)](#12-model-field-reference-all-tables)

---

# 1. Front Matter & Overview

## 1.1 Project Identity

**IIAP OM** is a unified, Django-based web platform designed for research and engineering organizations. It was originally scoped as a Project Management System for multi-disciplinary teams (Electronics, Mechanical, Optics, Simulation, Software) and has evolved into an **enterprise monolith** integrating document control, quality assurance, real-time chat, inventory management, financial tracking, and observatory telescope monitoring.

### Abstract / Executive Summary

IIAP OM eliminates operational fragmentation by providing a single authenticated environment where:

- Projects, requirements, tasks, and releases share a consistent ID scheme and relational model.
- Files are version-controlled, categorized, and snapshotted into immutable releases with checksums.
- Quality is enforced through test cases that gate task completion.
- Bugs follow a formal severity and resolution lifecycle.
- Teams communicate via WebSocket-powered chat (direct, group, and project rooms).
- Inventory staff operate in an isolated subdomain with separate credentials and audit trails.
- Observatory operators view and manage telescope status with granular permission flags.

The system is **server-rendered** for the primary UI (Django Templates + vanilla JavaScript) with **async real-time** capabilities via Django Channels and Daphne ASGI.

## 1.2 Core Goal

| Goal | Description |
|------|-------------|
| **Centralize** | One platform for PM, files, QA, chat, finance, inventory, and telescope ops |
| **Trace** | Dual audit logs, release immutability, requirement versioning |
| **Control access** | Role-based PM users + isolated inventory users + telescope permissions |
| **Automate** | Progress calculation, KB→file sync, notification generation, calendar sync |
| **Report** | Master reports (MD/PDF/DOCX/XLSX), RTM, test reports, Chart.js dashboards |

## 1.3 Target Problem Solved

| Pain Point | IIAP OM Solution |
|------------|------------------|
| Scattered spreadsheets and email threads | Unified `Project` → `Requirement` → `Task` hierarchy |
| Uncontrolled document versions | `ProjectFile` versioning + `ReleaseFile` SHA-256 snapshots |
| Untracked defects | Dedicated `bugs` app with threaded comments and resolution artifacts |
| Siloed team communication | WebSocket chat with presence, reactions, read receipts |
| Inventory vs PM credential mixing | `InventoryUser` model + `InventoryAccessMiddleware` |
| Compliance gaps | PM `AuditLog` (JSON diffs) + inventory `AuditLog.log()` |
| Release chaos | Publish/lock workflow, dual-approval file deletion |
| Observatory visibility | `Telescope` dashboard with per-instrument user flags |

## 1.4 Global Technology Stack

| Layer | Technology | Role |
|-------|------------|------|
| **Runtime** | Python 3.10+ | Application runtime |
| **Web Framework** | Django 4.2 | MVC, ORM, admin, sessions, forms |
| **ASGI Server** | Daphne | HTTP + WebSocket multiplexing |
| **Real-Time** | Django Channels 4.x | Chat consumers, live notifications |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Persistent relational storage |
| **Authentication** | Django session auth | Cookie-based login; no JWT in core PM paths |
| **Templates** | Django Template Language | Server-rendered HTML |
| **Frontend** | Vanilla HTML/CSS/JS | Dark theme; Space Grotesk + DM Sans fonts |
| **Charts** | Chart.js 4.4 | Dashboards and analytics |
| **Calendar UI** | FullCalendar.js 6.1 | Event visualization |
| **Icons** | Font Awesome 6.5 | UI iconography |
| **File Storage** | Django `FileField` / `MEDIA_ROOT` | Uploads (10 GB limit configured) |
| **PDF/Reports** | xhtml2pdf, fpdf, XlsxWriter, openpyxl | Export pipelines |
| **Calendar Sync** | Google Calendar API, CalDAV (Radicale) | External calendar integration |
| **AI (optional)** | google-generativeai | Analysis and report tooling |
| **API (available)** | djangorestframework | Installed; lightweight JSON endpoints in `tasks/api` |
| **Quality Tools** | pytest, pytest-django, black, flake8, bandit, coverage | CI-ready toolchain |
| **Debug** | django-debug-toolbar | Development profiling (`/__debug__/`) |

## 1.5 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Browser)                                 │
│   Django Templates │ Chart.js │ FullCalendar │ WebSocket (Chat / Presence)  │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │ HTTP / WebSocket
┌────────────────────────────────────▼─────────────────────────────────────────┐
│                         ASGI — Daphne (core/asgi.py)                          │
│              ProtocolTypeRouter: HTTP (Django) + WebSocket (Channels)         │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
     ┌───────────────────────────────┼───────────────────────────────┐
     ▼                               ▼                               ▼
┌─────────────┐              ┌───────────────┐              ┌───────────────┐
│ Middleware  │              │  URL Router   │              │ ChatConsumer  │
│ Security    │              │  core/urls.py │              │ chat/consumers│
│ Session     │              │  + app urls   │              │               │
│ CSRF        │              │               │              │               │
│ Auth        │              │               │              │               │
│ Inventory   │              │               │              │               │
│ Access      │              │               │              │               │
└──────┬──────┘              └───────┬───────┘              └───────┬───────┘
       │                             │                              │
       └─────────────────────────────┼──────────────────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │     Django ORM        │
                          │  SQLite / PostgreSQL  │
                          └──────────┬────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ MEDIA_ROOT /media   │
                          │ STATIC /static      │
                          └─────────────────────┘
```

## 1.6 Installed Applications

| Category | Django Apps |
|----------|-------------|
| **Infrastructure** | `daphne`, `channels`, `debug_toolbar` |
| **Django built-in** | `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles` |
| **PM & Collaboration** | `accounts`, `tasks`, `bugs`, `testcases`, `notes`, `files`, `finance`, `events`, `notifications`, `chat` |
| **Observatory** | `telescope` |
| **Inventory** | `inventory`, `products`, `stock`, `audit`, `reports`, `procurement`, `dashboard` |

---

# 2. Module-by-Module Breakdown

---

## 2.1 Core Configuration (`core`)

### Module Name & Purpose

The Django project package containing global settings, root URL routing, WSGI/ASGI entry points, and channel layer configuration.

### Engineering Style & Flow

- **Pattern:** Standard Django project layout
- **HTTP entry:** `manage.py` → `core.settings` → `core.urls`
- **ASGI entry:** `core/asgi.py` multiplexes HTTP and WebSocket protocols

### Key Configuration (`core/settings.py`)

| Setting | Value / Behavior |
|---------|------------------|
| `AUTH_USER_MODEL` | `accounts.User` |
| `LOGIN_URL` | `/accounts/login/` |
| `LOGIN_REDIRECT_URL` | `/dashboard/` |
| `TIME_ZONE` | `Asia/Kolkata` |
| `MEDIA_ROOT` | `BASE_DIR / "media"` |
| `STATIC_ROOT` | `BASE_DIR / "staticfiles"` |
| `CHANNEL_LAYERS` | `InMemoryChannelLayer` (use Redis in production) |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | 10 GB |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | `True` |

### Root URL Map (`core/urls.py`)

| Path | Included App |
|------|--------------|
| `/admin/` | Django Admin |
| `/accounts/` | `accounts` |
| `/files/` | `files` |
| `/finance/` | `finance` |
| `/` | `tasks` (PM core) |
| `/chat/` | `chat` |
| `/inventory/dashboard/` | `dashboard` |
| `/inventory/stock/` | `stock` |
| `/inventory/main/` | `inventory` |
| `/inventory/products/` | `products` |
| `/inventory/audit/` | `audit` |
| `/inventory/reports/` | `reports` |
| `/inventory/procurement/` | `procurement` |
| `/telescope/` | `telescope` |
| `/` (home) | Redirect → `tasks:dashboard` |

---

## 2.2 Accounts & Authentication (`accounts`)

### Module Name & Purpose

Central identity, session management, user CRUD, profile settings, telescope permission assignment, and dual-login routing (PM users vs inventory-only users).

### Engineering Style & Flow

| Pattern | Implementation |
|---------|----------------|
| Authentication | Django session-based login via `LoginForm` |
| Authorization | Role properties (`is_admin`, `is_project_manager`) + boolean flags |
| PM login | `POST /accounts/login/` → validate → check `can_access_pm` → `login()` |
| Inventory login | Sets `session['inv_user_id']` without PM session mixing |
| Guards | `@admin_required`, `@manager_or_admin_required` in `tasks/decorators.py` |
| Middleware | `InventoryAccessMiddleware` for inventory path isolation |

### Core Data Models

#### `User` (extends `AbstractUser`)

| Field Group | Fields |
|-------------|--------|
| **Identity** | `role`, `team`, `nickname`, `designation`, `phone`, `profile_picture`, `avatar_color` |
| **Roles** | `admin`, `project_manager`, `member`, `student` |
| **Teams** | `electronics`, `mechanical`, `optics`, `simulation`, `software`, `general` |
| **Access flags** | `can_access_pm`, `can_access_inventory`, `can_access_telescope`, `is_telescope_admin` |
| **Telescope ops** | `can_operate_vbt`, `can_operate_jcbt`, `can_operate_zeiss`, `can_operate_cassegrain`, `can_operate_schmidt`, `can_command_dome`, `can_trigger_exposures` |
| **Inventory compat** | `inventory_branch` FK, 15+ inventory permission booleans |
| **Preferences** | `theme_preference`, `email_notifications` |

### URL Endpoints (Representative)

| URL Name | Path | Description |
|----------|------|-------------|
| Login | `/accounts/login/` | PM user authentication |
| Logout | `/accounts/logout/` | Session termination |
| User list | `/accounts/users/` | Admin user management |
| Settings | `/accounts/settings/` | Profile and password change |
| Inventory login | `/accounts/inventory-login/` | Inventory-only session |

### Role Permission Matrix (PM)

| Feature | Admin | Project Manager | Member | Student |
|---------|:-----:|:---------------:|:------:|:-------:|
| Create users | Yes | No | No | No |
| Create projects | Yes | Yes | No | No |
| Edit/delete projects | Yes | Yes (own) | No | No |
| Create tasks | Yes | Yes | No | No |
| Edit tasks | Yes | Yes | No | No |
| View all tasks | Yes | Yes (team) | Yes (own) | Yes (own) |
| Report bugs | Yes | Yes | Yes | Yes |
| View reports | Yes | Yes | No | No |
| Update task status | Yes | Yes | Yes | Yes |
| Add comments | Yes | Yes | Yes | Yes |

---

## 2.3 Tasks — Project Management Core (`tasks`)

### Module Name & Purpose

The **heart of the PM system**: dashboard, projects, sub-modules, requirements, tasks (list/Kanban), sprints, releases/CI-CD, reports, trash, PM audit viewer, and URL mounting for bugs, calendar, notifications, test cases, and knowledge base.

### Engineering Style & Flow

| Component | Pattern |
|-----------|---------|
| Views | Function-based views split across packages: `dashboard_views`, `project_views`, `task_views`, `release_views`, `module_views`, `report_views`, `audit_views`, `misc_views` |
| Services | `report_engine.py`, `notification_service.py` |
| Signals | `signals.py` — auto `AuditLog` on save/delete/login |
| API | `tasks/api/endpoints.py` — JSON for AJAX |
| Context processors | `notifications_count`, `notes_count`, `system_settings`, `sidebar_projects` |
| Management | `seed_data` command for demo data |

### Core Data Models

#### `Project`

| Attribute | Detail |
|-----------|--------|
| ID format | `PRJ-{INITIALS}-{YEAR}-{####}` (auto-generated) |
| Status | planning, active, on_hold, completed, cancelled, archived |
| Visibility | private, public |
| Relations | `created_by`, `managers` (M2M), `project_incharge`, `members` (M2M) |
| Features | Progress bar (0–100), release workflow, soft-delete requests, cover image |

#### `ProjectModule` & `ModuleMember`

Sub-teams within a project. Member roles: `designer`, `developer`, `tester`.

#### `Requirement`

| Attribute | Detail |
|-----------|--------|
| ID format | `REQ-{PREFIX}-{YEAR}-{####}` |
| Types | BRD, FRD, TRD, UI/UX, security, API, database, non-functional |
| Status | draft → review → approved → implemented → verified |
| Features | M2M self-dependencies, versioning via `RequirementVersion`, trash support |

#### `Task`

| Attribute | Detail |
|-----------|--------|
| ID format | `{TYPE}-{PREFIX}-{YEAR}-{####}` (TAS, BUG, FEA, IMP, RES) |
| Status | todo, in_progress, review, done, blocked |
| Relations | `project`, `requirement`, `module`, `release`, `parent_task`, `sprint` |
| Gating | `can_complete` requires all linked test cases to pass |
| Features | Subtasks, tags, story points, estimated/actual hours, trash |

#### `Release` & `ReleaseFile`

| Feature | Detail |
|---------|--------|
| Types | partial (minor/nightly), phase (major) |
| Immutability | Locked when `status == completed` |
| Snapshots | `ReleaseFile` stores frozen copy with SHA-256 `content_hash` |
| Workflow | Draft → publish → lock; deletion requests require admin resolution |

#### Other PM Models

| Model | Purpose |
|-------|---------|
| `Comment` | Threaded task comments with attachments |
| `Sprint` | Agile sprint windows per project |
| `PipelineRun` | CI/CD run tracking (pending/running/passed/failed) |
| `ModuleForumPost` | Module-level discussion forum |
| `SystemIssue` | Platform-level bug/feature requests |
| `SystemSettings` | Global theme colors, default passwords |
| `AuditLog` | PM audit trail (see Section 2.15) |

### Progress Calculation Algorithm

```
For each active task in project:
  - Base weight from status: done=100%, review=80%, in_progress=30%
  - If test cases exist: final = (status_weight × 0.6) + (TC_pass% × 0.4)
  - Else: final = status_weight
Project progress = average of all task weights
```

### Key URL Routes

| Route | Name | Function |
|-------|------|----------|
| `/dashboard/` | `dashboard` | Main PM dashboard |
| `/projects/` | `project_list` | All projects |
| `/projects/<pk>/` | `project_detail` | Project hub |
| `/tasks/` | `task_list` | Global task list |
| `/tasks/<pk>/` | `task_detail` | Task detail + comments |
| `/releases/` | `global_release_list` | All releases |
| `/report-center/` | `report_center` | Analytics hub |
| `/audit-logs/` | `audit_log_list` | PM audit viewer |
| `/trash/` | `trash` | Soft-deleted items |
| `/knowledge-base/` | `kb_overview` | Notes hub |

---

## 2.4 Bugs (`bugs`)

### Module Name & Purpose

Formal defect tracking decoupled from generic tasks but linkable via `linked_task`. Supports severity classification, assignment, resolution artifacts, and threaded comments.

### Engineering Style & Flow

- **Views:** `bugs/views.py` (FBV)
- **URLs:** Mounted under `tasks` namespace at `/bugs/`
- **Forms:** `bugs/forms.py`
- **Trash:** Soft-delete with restore via `misc_views`

### Core Data Models

#### `BugReport`

| Field | Values / Notes |
|-------|----------------|
| `severity` | low, medium, high, critical |
| `status` | open, in_progress, resolved, closed, wont_fix |
| `assignees` | ManyToMany → User |
| `linked_task` | Optional FK → Task |
| Resolution | `resolution_summary`, `solving_results`, `resolution_attachment`, `resolved_by` |

#### `BugComment`

Threaded via `parent` FK. Supports file attachments.

**Legacy tables:** `tasks_bugreport`, `tasks_bugcomment` (migration compatibility).

### URL Routes

| Route | Action |
|-------|--------|
| `/bugs/` | List all bugs |
| `/bugs/new/` | Create bug |
| `/bugs/<pk>/` | Bug detail |
| `/bugs/<pk>/resolve/` | Resolution workflow |
| `/bugs/<pk>/comment/` | Add comment |

---

## 2.5 Test Cases (`testcases`)

### Module Name & Purpose

Formal QA test management tied to projects and tasks. **Blocks task completion** until all linked test cases pass.

### Engineering Style & Flow

- Views: `testcases/views.py`
- URLs: Under `tasks:` namespace
- Verification: assign → execute → verify → approval

### Core Data Models

#### `TestCase`

| Field | Detail |
|-------|--------|
| `test_id` | `{PROJECT_PREFIX}-TC-{YEAR}-{######}` |
| `status` | pending, passed, failed, blocked, retest |
| `approval_status` | pending, approved, rejected |
| Relations | FK → Project, FK → Task, M2M → assigned_members |

#### `TestCaseAttachment` / `TestCaseHistory`

Evidence files and action audit per test case.

### Task Completion Gate

```python
@property
def can_complete(self):
    test_cases = self.test_cases.all()
    if not test_cases.exists():
        return True
    return test_cases.filter(status="passed").count() == test_cases.count()
```

---

## 2.6 Notes / Knowledge Base (`notes`)

### Module Name & Purpose

Markdown knowledge base per project/module. **Auto-syncs** to `files.ProjectFile` under a `Notes` category on every save.

### Engineering Style & Flow

- CRUD views with access control (`kb_access`)
- Model `save()` creates/updates `.md` in project file tree
- Integrated with files module for unified document browsing

### Core Data Model — `KnowledgeBaseNote`

| Field | Description |
|-------|-------------|
| `title` | Note title |
| `content` | Markdown body |
| `project` | Optional FK → Project |
| `module` | Optional FK → ProjectModule |
| Trash | `is_in_trash`, `deleted_at`, `deleted_by` |

---

## 2.7 Files & Document Management (`files`)

### Module Name & Purpose

Enterprise file repository: hierarchical categories, versioning, access rights, inline preview, folder ZIP download, document/folder discussion, trash with dual-approval deletion.

### Engineering Style & Flow

| Package | Responsibility |
|---------|----------------|
| `file_list_views.py` | Browse, filter, search |
| `detail_views.py` | Preview, discussion, annotations |
| `manage_views.py` | Upload, edit, move, trash |
| `access_views.py` | Permission management |

**Upload path:** `media/projects/<PRJ-ID>/<category-tree>/<filename>`

### Core Data Models

#### `FileCategory`

Tree structure via `parent` self-FK. Unique per `(name, parent, project)`.

#### `ProjectFile`

| Feature | Detail |
|---------|--------|
| Versioning | `parent_file` FK chain; `version` integer |
| Type detection | image, pdf, document, spreadsheet, presentation, code, archive, video, audio, CAD |
| Relations | project, module, release, task, requirement, category |
| Security | `is_public` flag; `DocumentAccessRight` per user |
| Trash | Dual approval: `admin_approved_deletion` + `pm_approved_deletion` |
| Preview | Inline browser preview for supported types |

#### `FileComment`

Discussion and PDF annotation coordinates (`annotation_coords`).

### URL Routes

| Route | Action |
|-------|--------|
| `/files/` | Global file list |
| `/files/upload/` | Upload form |
| `/files/<pk>/` | File detail/preview |
| `/files/project/<pk>/` | Project file browser |
| `/files/audit-logs/` | File-specific audit |

---

## 2.8 Finance (`finance`)

### Module Name & Purpose

Per-project budget and expense tracking with receipt linking to project files.

### Engineering Style & Flow

Simple FBV under `/finance/project/<id>/`.

### Core Data Models

| Model | Relations | Computed |
|-------|-----------|----------|
| `Budget` | OneToOne → Project | `total_expenses`, `remaining_budget` |
| `Expense` | FK → Project; optional FK receipt → ProjectFile | Categories: hardware, software, travel, services, materials, other |

### URL Routes

| Route | Action |
|-------|--------|
| `/finance/project/<id>/` | Expense list |
| `/finance/project/<id>/expense/add/` | Log expense |
| `/finance/project/<id>/budget/` | Edit budget |

---

## 2.9 Events & Calendar (`events`)

### Module Name & Purpose

Project/task-linked calendar with FullCalendar.js UI and external sync (Google Calendar OAuth + CalDAV/Radicale).

### Engineering Style & Flow

| Component | Role |
|-----------|------|
| `calendar_view` | FullCalendar front-end |
| `google_calendar_init/callback` | OAuth token storage |
| `toggle_caldav_sync` | Radicale integration |
| `tasks/calendar_sync.py` | Sync engine |

### Core Data Models

#### `CalendarEvent`

| Field | Detail |
|-------|--------|
| `event_type` | milestone, meeting, deadline, review, other |
| Relations | Optional FK → Project, Task |
| Sync IDs | `google_event_id`, `caldav_event_path` |
| Meeting | `meeting_link`, `meeting_password`, `location` |

#### `UserCalendarSettings`

Per-user OAuth token (JSON), CalDAV credentials, sync flags.

---

## 2.10 Notifications (`notifications`)

### Module Name & Purpose

In-app alerts for task events, test results, chat messages, and bugs. Optional real-time push via Channels.

### Engineering Style & Flow

- Factory: `NotificationService.create_notification()`
- Channel group: `user_{recipient_id}` for live unread count
- Context processor: `notifications_count` in sidebar

### Notification Types

| Type | Trigger |
|------|---------|
| `task_assigned` | Task assignment |
| `task_updated` | Task field change |
| `task_completed` | Status → done |
| `comment_added` | New task comment |
| `due_soon` / `overdue` | Date-based |
| `test_assigned` / `test_failed` / `test_approved` | QA workflow |
| `chat_message` | New chat message |
| `bug_reported` | New bug |

---

## 2.11 Chat & Real-Time Messaging (`chat`)

### Module Name & Purpose

Real-time messaging: direct messages, group chats, project rooms, file/voice attachments, reactions, read receipts, presence, forwarding.

### Engineering Style & Flow

| Layer | Technology |
|-------|------------|
| HTTP API | `chat/views.py` — messages, upload, search, clear |
| WebSocket | `ChatConsumer` (AsyncWebsocketConsumer) |
| Routing | `ws/chat/<room_id>/` via `chat/routing.py` |
| ASGI | `ProtocolTypeRouter` in `core/asgi.py` |
| Channel layer | InMemory (dev) — **Redis required for production** |

### Core Data Models

| Model | Purpose |
|-------|---------|
| `ChatRoom` | UUID PK; types: direct, group, project |
| `Message` | text, file, voice, task_link, system |
| `MessageReaction` | Emoji reactions (unique per user+emoji) |
| `ChatAttachment` | File metadata; auto-delete on record delete |
| `ReadReceipt` | Per-user read tracking |
| `UserPresence` | Online/offline status |
| `ChatClear` | Per-user "cleared at" timestamp |

### DM Room Normalization

Direct message rooms use normalized name `DM-{min_id}-{max_id}` so both participants join the same WebSocket group.

---

## 2.12 Telescope Operations (`telescope`)

### Module Name & Purpose

Observatory dashboard for VBO telescopes with granular per-instrument permissions on the PM `User` model.

### Engineering Style & Flow

- FBV: dashboard, detail, CRUD
- Access: `can_access_telescope` flag
- Admin CRUD: `is_telescope_admin` or platform admin

### Core Data Model — `Telescope`

| Field | Example |
|-------|---------|
| `id_name` | `vbt_234` |
| `name` | VBT 2.34m Reflector |
| `aperture` | 2.34 Meter |
| `status` | observing, idle, maintenance |
| `current_target` | M31 |
| `ra` / `dec` | Coordinate strings |
| `dome` | Open / Closed |
| `ccd_temp` | -10°C |
| `tracking` | Enabled / Disabled |

### URL Routes

| Route | Action |
|-------|--------|
| `/telescope/` | Dashboard (all telescopes) |
| `/telescope/<pk>/` | Detail view |
| `/telescope/create/` | Add telescope (admin) |
| `/telescope/<pk>/edit/` | Edit |
| `/telescope/<pk>/delete/` | Delete |

---

## 2.13 Inventory Subsystem

The inventory domain spans **seven Django apps** with shared middleware and a separate user model.

### 2.13.1 `inventory` — Core Stock Logic

| Model | Purpose |
|-------|---------|
| `Branch` | Multi-site locations (code, name, address) |
| `BranchStock` | Per-branch quantity, rack/shelf, low-stock limit |
| `InventoryAdjustment` | Manual/automated quantity corrections |
| `SerialNumber` | Serialized asset tracking (available/sold/returned/damaged) |
| `QuantityLimit` | Threshold alerts |
| `Alert` | Stock alert records |
| `Rental` | Equipment rental tracking |
| `StandardLimit` | Global standard limits |
| `InventoryUser` | **Separate auth model** (not Django User) |
| `InventoryNotification` | In-app inventory alerts |
| `SystemSettings` | Inventory module configuration |

#### `InventoryUser` Roles

| Role | Capabilities |
|------|--------------|
| `super_admin` | All branches, user management |
| `branch_admin` | Single branch administration |
| `staff` | Limited operations per flags |

### 2.13.2 `products` — Catalog

| Model | Fields |
|-------|--------|
| `Category` | name, description, image; 9 default categories seeded |
| `Product` | name, SKU, serial, price, unit, status, branch, datasheet |

### 2.13.3 `stock` — Movements

| Model | Purpose |
|-------|---------|
| `StockEntry` | Stock in / out / transfer entries |
| `StockTransfer` | Inter-branch transfer (pending → received) |

### 2.13.4 `procurement` — Purchasing

`ProcurementRequest`: requester → product → branch → approval workflow with `fulfilled_quantity`.

### 2.13.5 `audit` — Inventory Audit

Static `AuditLog.log(user, action, instance, changes)` — branch-scoped.

### 2.13.6 `dashboard` & `reports`

KPI dashboard and exportable branch-filtered reports.

### Inventory Middleware Flow

```
Request to /inventory/*
    │
    ├─ inv_user_id in session? → request.user = InventoryUser
    ├─ PM user with can_access_inventory? → allow
    └─ else → redirect to login

Inventory-only user accessing PM path?
    └─ redirect to /inventory/dashboard/
```

### Inventory URL Prefixes

| Prefix | App |
|--------|-----|
| `/inventory/dashboard/` | dashboard |
| `/inventory/main/` | inventory (adjustments, serials, limits, alerts, rentals, shortage) |
| `/inventory/stock/` | stock |
| `/inventory/products/` | products |
| `/inventory/audit/` | audit |
| `/inventory/reports/` | reports |
| `/inventory/procurement/` | procurement |

---

## 2.14 Media Storage Layer

Not a Django app — the filesystem layer at `MEDIA_ROOT = BASE_DIR / "media"`.

### Directory Structure

```
media/
├── avatars/                    # User profile pictures
├── room_avatars/               # Chat room images
├── project_images/             # Project cover images
├── projects/                   # Project files (mirrors FileCategory tree)
│   └── PRJ-XX-2026-####/
│       ├── Specifications/
│       ├── Releases/
│       └── Notes/
├── releases/                   # Immutable release snapshots
├── resources/notes/            # KB note .md exports
├── chat_attachments/           # Chat file uploads
├── bugs/                       # Bug resolution & comment files
│   ├── resolutions/
│   └── comments/
├── test_cases/attachments/     # Test evidence
├── telescopes/                 # Telescope images
├── product_images/             # Inventory catalog images
├── product_datasheets/         # Product datasheets
├── comments/                   # Task comment attachments
└── uploads/                    # Fallback uncategorized uploads
```

**Serving:** `/media/` via Django static helper in DEBUG; production requires Nginx with optional authenticated download views.

---

## 2.15 Dual Audit Systems

| Aspect | PM Audit (`tasks.AuditLog`) | Inventory Audit (`audit.AuditLog`) |
|--------|----------------------------|-------------------------------------|
| **User FK** | `accounts.User` | `inventory.InventoryUser` |
| **Storage** | JSON `old_value` / `new_value` | Text `changes` |
| **Trigger** | Django signals + manual | `AuditLog.log()` static helper |
| **Viewer** | `/audit-logs/` | `/inventory/audit/` |
| **Modules** | project, requirement, task, test_case, bug, release, user, system, file, folder | Product, Stock, Branch operations |
| **Actions** | create, update, delete, login, logout, approve, reject, publish, restore, upload, download, move | Free-text action string |
| **IP tracking** | Yes (`ip_address`, `user_agent`) | No |

---

# 3. System Design & Visual Architecture

## 3.1 Complete Directory Structure

```
IIA Management/
├── core/                           # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
├── pytest.ini
├── db.sqlite3
│
├── accounts/                       # Authentication & users
│   ├── models.py
│   ├── forms.py
│   ├── middleware.py
│   ├── urls.py
│   └── views/
│       ├── auth_views.py
│       ├── profile_views.py
│       └── user_management_views.py
│
├── tasks/                          # PM core
│   ├── models.py
│   ├── urls.py
│   ├── signals.py
│   ├── decorators.py
│   ├── context_processors.py
│   ├── calendar_sync.py
│   ├── views/                      # Split view modules
│   ├── services/
│   ├── api/
│   └── management/commands/seed_data.py
│
├── bugs/                           # Bug tracking
├── testcases/                      # QA test cases
├── notes/                          # Knowledge base
├── files/                          # Document management
│   └── views/
├── finance/                        # Budget & expenses
├── events/                         # Calendar
├── notifications/                  # Alerts
├── chat/                           # Real-time messaging
│   ├── models.py
│   ├── consumers.py
│   ├── routing.py
│   └── templates/chat/
├── telescope/                      # Observatory dashboard
│
├── inventory/                      # Stock core
├── products/                       # Product catalog
├── stock/                          # Stock movements
├── procurement/                    # Purchase requests
├── audit/                          # Inventory audit
├── dashboard/                      # Inventory dashboard
├── reports/                        # Inventory reports
│
├── templates/                      # Global templates
│   ├── base.html
│   ├── core_base.html
│   ├── inventory_base.html
│   ├── accounts/
│   ├── tasks/
│   ├── files/
│   ├── bugs/
│   └── telescope/
├── static/                         # CSS, JS, images
├── media/                          # User uploads (runtime)
└── project_documentation/          # Technical docs
    ├── PROJECT_REPORT.md           # This document
    └── class_diagram.md
```

## 3.2 Data Flow Diagram — Task Status Update

```
┌──────────────┐
│ User clicks  │
│ status change│
└──────┬───────┘
       │ POST /tasks/<pk>/status/
       ▼
┌──────────────────┐
│ CSRF validation  │
└────────┬─────────┘
         ▼
┌──────────────────┐     ┌─────────────────────┐
│ task_update_     │────►│ Permission check    │
│ status view      │     │ (role / assignee)   │
└────────┬─────────┘     └─────────────────────┘
         ▼
┌──────────────────┐
│ Task.save()      │
│ - set completed_at│
│ - generate task_id│
└────────┬─────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    ▼         ▼              ▼             ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Project │ │Notifica- │ │ signals  │ │ Channels │
│.update_│ │tionServ- │ │ AuditLog │ │ (optional)│
│progress│ │ice       │ │ .create  │ │ push     │
└────────┘ └──────────┘ └──────────┘ └──────────┘
         │
         ▼
┌──────────────────┐
│ JSON or redirect │
│ response to UI   │
└──────────────────┘
```

## 3.3 Data Flow Diagram — File Upload

```
Browser (multipart/form-data)
    │
    ▼ POST /files/upload/
file_upload view
    │
    ├─ Validate project membership
    ├─ Resolve FileCategory (tree path)
    ├─ Detect file type from extension
    ├─ Create ProjectFile record
    │     └─ upload_to() → media/projects/PRJ-ID/.../filename
    ├─ If version bump: link parent_file, increment version
    └─ AuditLog (upload action)
    │
    ▼
Redirect to project file browser or file detail
```

## 3.4 Data Flow Diagram — WebSocket Chat

```
Browser WebSocket connect → ws/chat/<room_id>/
    │
    ▼
ChatConsumer.connect()
    ├─ Auth check (scope["user"])
    ├─ Resolve ChatRoom (DM normalization for direct)
    ├─ channel_layer.group_add("chat_{room_id}")
    ├─ Update UserPresence (online)
    └─ Mark messages read, broadcast presence
    │
    ▼ (on message)
ChatConsumer.receive()
    ├─ Save Message to DB
    ├─ group_send to room
    └─ Create Notification for offline participants
    │
    ▼
All connected clients receive JSON message event
```

## 3.5 Database Relational Blueprint — PM Core

```
                    ┌─────────────────┐
                    │      User       │
                    │   (accounts)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │ M2M          │ M2M          │ FK created_by
              ▼              ▼              ▼
       ┌─────────────┐  ┌───────────┐  ┌─────────────┐
       │   Project   │  │  managers │  │   members   │
       │ PRJ-XX-YYYY │──│  (M2M)    │  │   (M2M)     │
       └──────┬──────┘  └───────────┘  └─────────────┘
              │
    ┌─────────┼─────────┬────────────┬──────────────┐
    │         │         │            │              │
    ▼         ▼         ▼            ▼              ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│Project │ │Require-│ │  Task    │ │ Release│ │ProjectFile│
│Module  │ │ ment   │ │TAS-XX-YY │ │        │ │          │
└───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └────┬─────┘
    │          │           │           │           │
    │          │      ┌────┴────┐      │      ┌────┴─────┐
    │          │      │         │      │      │FileCategory│
    │          │      ▼         ▼      ▼      └──────────┘
    │          │  ┌───────┐ ┌────────┐ ┌────────────┐
    │          │  │Comment│ │TestCase│ │ReleaseFile │
    │          │  └───────┘ └────────┘ └────────────┘
    │          │
    │          └──────► BugReport (optional linked_task)
    │
    └──────► ModuleMember (user + role)

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ChatRoom   │──1:N│   Message   │     │ Notification│
│  (UUID PK)  │     └─────────────┘     │  → User     │
└─────────────┘                         └─────────────┘

┌─────────────┐  1:1  ┌─────────────┐  1:N  ┌─────────────┐
│   Project   │──────►│   Budget    │──────►│   Expense   │
└─────────────┘       └─────────────┘       └─────────────┘
```

## 3.6 Database Relational Blueprint — Inventory

```
┌─────────────┐
│   Branch    │
└──────┬──────┘
       │
       ├──────────────────────────────────────────┐
       │                                          │
       ▼                                          ▼
┌─────────────┐    N:1    ┌─────────────┐   ┌─────────────┐
│ BranchStock │◄──────────│   Product   │──►│  Category   │
└─────────────┘           └──────┬──────┘   └─────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────────┐
              │StockEntry│ │SerialNum │ │ProcurementReq│
              └──────────┘ └──────────┘ └──────────────┘
                    │
                    ▼
              ┌──────────────┐
              │StockTransfer │
              │ (branch A→B) │
              └──────────────┘

┌───────────────┐         ┌─────────────┐
│ InventoryUser │──N:1───►│   Branch    │
└───────┬───────┘         └─────────────┘
        │
        ▼
┌─────────────┐
│  AuditLog   │  (inventory.audit)
└─────────────┘
```

## 3.7 Context Processors (Global Template Data)

| Processor | Data Provided |
|-----------|---------------|
| `notifications_count` | Unread PM notification count |
| `notes_count` | KB notes count |
| `system_settings` | Theme colors, font size |
| `sidebar_projects` | Recent projects for navigation |
| `inventory_notifications_count` | Unread inventory notifications |

---

# 4. Technical Implementation & Security

## 4.1 Critical Code — Project Progress with Test-Case Blending

```python
# tasks/models.py — Project.update_progress()
def update_progress(self):
    tasks = self.tasks.filter(is_in_trash=False)
    total_tasks = tasks.count()
    if total_tasks == 0:
        self.progress = 0
    else:
        total_progress = 0
        for task in tasks:
            task_weight = 0
            if task.status == "done":
                task_weight = 100
            elif task.status == "review":
                task_weight = 80
            elif task.status == "in_progress":
                task_weight = 30

            stats = task.test_case_stats
            if stats["total"] > 0:
                tc_factor = stats["percentage"]
                task_weight = int((task_weight * 0.6) + (tc_factor * 0.4))

            total_progress += task_weight

        self.progress = int(total_progress / total_tasks)
    self.save(update_fields=["progress"])
```

## 4.2 Critical Code — PM Audit on Login

```python
# tasks/signals.py
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if isinstance(user, User):
        AuditLog.objects.create(
            user=user,
            action_type='login',
            module='user',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=f"User {user.username} logged in."
        )
```

## 4.3 Critical Code — Release Immutability

```python
# tasks/models.py — Release.save()
def save(self, *args, **kwargs):
    if self.pk:
        old_instance = Release.objects.get(pk=self.pk)
        if old_instance.is_locked:
            raise ValidationError(
                "This release is locked and cannot be modified."
            )
    super().save(*args, **kwargs)
```

## 4.4 Critical Code — Knowledge Base → File Sync

```python
# notes/models.py — KnowledgeBaseNote.save() (excerpt)
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    if self.project:
        notes_cat, _ = FileCategory.objects.get_or_create(
            name="Notes", project=self.project,
            defaults={"created_by": self.author}
        )
        file_name = f"{self.title}.md".replace("/", "-")
        # Create or update ProjectFile with markdown content
        ...
```

## 4.5 Critical Code — WebSocket Chat Consumer (Connect)

```python
# chat/consumers.py — ChatConsumer.connect() (excerpt)
async def connect(self):
    self.user = self.scope["user"]
    if not self.user.is_authenticated:
        await self.close()
        return
    # Resolve room, join channel group, update presence
    await self.channel_layer.group_add(
        self.room_group_name, self.channel_name
    )
    await self.accept()
    await self.update_user_presence(True)
```

## 4.6 Critical Code — Inventory Audit Helper

```python
# audit/models.py
@staticmethod
def log(user, action, instance=None, changes=None):
    branch = getattr(user, "branch", None)
    if instance and hasattr(instance, "branch"):
        branch = instance.branch
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=instance.__class__.__name__ if instance else "System",
        object_id=getattr(instance, "pk", 0) or 0,
        changes=changes or "",
        branch=branch,
    )
```

## 4.7 Security Measures

| Concern | Implementation |
|---------|----------------|
| **Authentication** | Django sessions; `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` |
| **Authorization** | Role decorators; `Project.is_manager()`; `DocumentAccessRight` |
| **CSRF** | `CsrfViewMiddleware` on all POST forms |
| **Clickjacking** | `XFrameOptionsMiddleware` |
| **PM/Inventory isolation** | `InventoryAccessMiddleware` + separate `InventoryUser` |
| **Password policy** | Django validators (length, common, similarity, numeric) |
| **Access flags** | `can_access_pm`, `can_access_inventory`, telescope flags |
| **File security** | `is_public`; dual-approval trash; release SHA-256 |
| **Audit trail** | Login IP/user-agent; JSON change tracking |
| **Inactive users** | Blocked at login with error message |

## 4.8 Production Security Checklist

- [ ] Replace `SECRET_KEY` in `core/settings.py`
- [ ] Set `DEBUG = False`
- [ ] Restrict `ALLOWED_HOSTS` to production domain(s)
- [ ] Migrate database to PostgreSQL
- [ ] Enable HTTPS; set `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- [ ] Configure Redis for `CHANNEL_LAYERS`
- [ ] Remove `debug_toolbar` from `INSTALLED_APPS`
- [ ] Run `python manage.py collectstatic`
- [ ] Serve sensitive media via authenticated views or signed URLs
- [ ] Rotate `client_secret.json` and store outside repository

## 4.9 Performance Optimization

| Area | Technique |
|------|-----------|
| ORM queries | `select_related` / `prefetch_related` in list views |
| SQLite | `timeout: 20` in DATABASE OPTIONS |
| Notifications | Indexed `-created_at`; scoped to `recipient` |
| Files | Query `versions__isnull=True` for latest versions only |
| Channels | Redis channel layer for multi-worker deployments |
| Static assets | `collectstatic` + CDN/Nginx caching |
| Uploads | Stream large files; consider S3 for scale |

---

# 5. Testing & Deployment

## 5.1 Test Case Matrix

| TC-ID | Module | Input / Action | Expected Outcome | Pass Criteria |
|-------|--------|----------------|------------------|---------------|
| TC-ACC-01 | accounts | Valid admin login (`admin`/`admin123`) | Redirect to dashboard | HTTP 302 → `/dashboard/`; session key set |
| TC-ACC-02 | accounts | User with `can_access_pm=False` | Access denied | Error flash; remains on login page |
| TC-ACC-03 | accounts | Admin creates telescope user | User with telescope flags | DB record; flags verified |
| TC-ACC-04 | accounts | Inventory login with valid credentials | Session `inv_user_id` set | Redirect to `/inventory/dashboard/` |
| TC-ACC-05 | accounts | Inventory user accesses `/dashboard/` | Blocked | Redirect to inventory dashboard |
| TC-PRJ-01 | tasks | Create project "Solar Array" | Auto ID generated | Matches `PRJ-SA-2026-####` |
| TC-PRJ-02 | tasks | Project with 0 tasks | Progress = 0 | `project.progress == 0` |
| TC-PRJ-03 | tasks | Archive project | `is_archived=True` | Toggle succeeds |
| TC-REQ-01 | tasks | Create requirement | REQ ID auto-generated | Unique `req_id` in DB |
| TC-TSK-01 | tasks | PM updates task status via POST | Status saved | DB + progress updated |
| TC-TSK-02 | tasks | Member updates another's task | Denied | Redirect + error message |
| TC-TSK-03 | tasks | Complete task with failing TCs | Blocked | `can_complete == False` |
| TC-TSK-04 | tasks | Complete task with all TCs passed | Allowed | `can_complete == True` |
| TC-BUG-01 | bugs | Create bug on project | Bug in project list | FK valid; appears in UI |
| TC-BUG-02 | bugs | Resolve bug with attachment | Status=resolved | Resolution fields populated |
| TC-TC-01 | testcases | Verify test case | `verified_by` set | Status updated |
| TC-FIL-01 | files | Upload PDF to category | File on disk | Path under `media/projects/` |
| TC-FIL-02 | files | Upload v2 of same file | Version chain | `parent_file` linked; version=2 |
| TC-FIL-03 | files | Delete file (soft) | `is_in_trash=True` | Appears in trash view |
| TC-REL-01 | tasks | Publish release | Snapshots created | `ReleaseFile` rows with checksums |
| TC-REL-02 | tasks | Edit completed release | Error | `ValidationError` raised |
| TC-NOT-01 | notifications | Assign task to user | Notification created | Unread count +1 |
| TC-CHT-01 | chat | WS connect without auth | Connection closed | Consumer closes immediately |
| TC-CHT-02 | chat | Send DM message | Both users receive | Message in DB; WS delivered |
| TC-EVT-01 | events | Create calendar event | Event in FullCalendar | Correct start/end |
| TC-FIN-01 | finance | Add expense | Expense logged | `Budget.remaining_budget` updated |
| TC-INV-01 | inventory | Stock in entry | Quantity increases | `BranchStock.current_quantity` correct |
| TC-INV-02 | inventory | Cross-branch transfer | Transfer pending → received | Status workflow complete |
| TC-INV-03 | inventory | Procurement approve | Status=approved | `decided_by` set |
| TC-AUD-01 | audit | Update product | Inventory audit row | `model_name == Product` |
| TC-AUD-02 | tasks | Login as PM user | PM audit login row | `action_type == login` |
| TC-TEL-01 | telescope | User without telescope access | Denied | No dashboard access |
| TC-TEL-02 | telescope | Admin creates telescope | Record saved | Dashboard shows instrument |
| TC-RPT-01 | tasks | Download master report XLSX | File response | Correct Content-Type |
| TC-KB-01 | notes | Save KB note | `.md` file in project | `ProjectFile` under Notes category |
| TC-TRSH-01 | tasks | Restore task from trash | `is_in_trash=False` | Task visible in list |

## 5.2 Running Tests

```bash
cd "/media/Data/Saran Projects/IIA Management"
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest --ds=core.settings -v
```

### Existing Test Suites

| File | Coverage |
|------|----------|
| `accounts/tests.py` | User management, telescope user CRUD |
| `tasks/tests.py` | ID generation, KB sync, permissions, master reports |
| `telescope/tests.py` | Telescope CRUD, access control |
| `inventory/tests.py` | Adjustments, serial numbers |
| `products/tests.py` | Categories, products |
| `stock/tests.py` | Stock in entries |
| `audit/tests.py` | Audit log listing |
| `dashboard/tests.py` | Dashboard overview |

## 5.3 Deployment Topology

```
                         ┌─────────────────────────┐
                         │    Internet / LAN        │
                         └───────────┬─────────────┘
                                     │
                         ┌───────────▼─────────────┐
                         │   Nginx Reverse Proxy    │
                         │   - TLS (Let's Encrypt)  │
                         │   - /static/ → cached    │
                         │   - /media/  → storage   │
                         │   - proxy → Daphne :8001 │
                         └───────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │ Daphne (ASGI)  │    │  PostgreSQL    │    │     Redis      │
     │ Django 4.2     │◄──►│  (production)  │    │ Channel Layer  │
     │ + Channels     │    └────────────────┘    └────────────────┘
     └────────┬───────┘
              │
              ▼
     ┌────────────────┐         ┌────────────────┐
     │  File Storage  │         │  Radicale      │
     │  local / S3    │         │  CalDAV :5232  │
     └────────────────┘         └────────────────┘
```

## 5.4 Deployment Steps

```bash
# 1. Environment
export DJANGO_SETTINGS_MODULE=core.settings
export DEBUG=False

# 2. Dependencies
pip install -r requirements.txt
pip install gunicorn psycopg2-binary redis

# 3. Database
python manage.py migrate

# 4. Static files
python manage.py collectstatic --noinput

# 5. Start ASGI server
daphne -b 0.0.0.0 -p 8001 core.asgi:application

# 6. (Alternative) WSGI-only without WebSocket
gunicorn core.wsgi:application -b 0.0.0.0:8000 -w 4
```

## 5.5 Environment Comparison

| Aspect | Development | Production |
|--------|-------------|------------|
| Server | `runserver` / Daphne | Nginx + Daphne |
| Database | SQLite | PostgreSQL |
| Channels | InMemoryChannelLayer | Redis |
| DEBUG | True | False |
| Media | Local `/media/` | S3 or protected Nginx |
| Toolbar | Enabled | Disabled |

## 5.6 Future Scope

| Priority | Enhancement |
|----------|-------------|
| **High** | PostgreSQL + Redis Channels in production |
| **High** | REST API (DRF) for mobile/SPA clients |
| **Medium** | S3-compatible object storage for media |
| **Medium** | Elasticsearch for global search |
| **Medium** | Webhook-driven `PipelineRun` from Git CI |
| **Low** | Live telescope telemetry feeds (replace static fields) |
| **Low** | Kubernetes deployment for multi-branch inventory |

---

# 6. Appendices

## Appendix A — Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Project Manager | pm_raj | pass123 |
| Project Manager | pm_sara | pass123 |
| Member | arjun_elec | pass123 |
| Member | priya_sw | pass123 |
| Member | vikram_mech | pass123 |
| Member | ananya_opt | pass123 |
| Member | suresh_sim | pass123 |

**Seed command:** `python manage.py seed_data`

## Appendix B — ID Format Reference

| Entity | Format | Example |
|--------|--------|---------|
| Project | `PRJ-{INIT}-{YEAR}-{####}` | `PRJ-S-2026-0021` |
| Requirement | `REQ-{PREFIX}-{YEAR}-{####}` | `REQ-S-2026-0003` |
| Task | `{TYPE}-{PREFIX}-{YEAR}-{####}` | `TAS-S-2026-0042` |
| Test Case | `{PREFIX}-TC-{YEAR}-{######}` | `PRJ-TC-2026-000015` |

## Appendix C — Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| Django | Web framework |
| channels, daphne | WebSocket / ASGI |
| Pillow | Image processing |
| openpyxl, xlrd, XlsxWriter | Spreadsheet I/O |
| xhtml2pdf, fpdf | PDF generation |
| djangorestframework | REST API (available) |
| google-api-python-client | Google Calendar |
| caldav, radicale | CalDAV sync |
| google-generativeai | AI analysis |
| pytest, pytest-django | Testing |
| black, flake8, bandit, pylint, safety, coverage | Quality tooling |

## Appendix D — Quick Start

```bash
cd "IIA Management"
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
# Open http://127.0.0.1:8000/
```

## Appendix E — Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | May 29, 2026 | Initial complete project report |
| 2.0 | May 29, 2026 | Added URL encyclopedia, forms, templates, logic flows, model reference, code encyclopedia companion |

---

# 7. Complete URL Route Encyclopedia

All routes discovered from `core/urls.py` and app `urls.py` files. **Template name** = Django `{% url %}` namespace.

## 7.1 Root & Core (`core/urls.py`)

| URL | Namespace:Name | Handler |
|-----|----------------|---------|
| `/admin/` | admin | Django Admin |
| `/accounts/*` | accounts:* | accounts.urls |
| `/files/*` | files:* | files.urls |
| `/finance/*` | finance:* | finance.urls |
| `/` | tasks:* | tasks.urls (PM core) |
| `/chat/*` | chat:* | chat.urls |
| `/inventory/dashboard/*` | dashboard:* | dashboard.urls |
| `/inventory/stock/*` | stock:* | stock.urls |
| `/inventory/main/*` | inventory:* | inventory.urls |
| `/inventory/products/*` | products:* | products.urls |
| `/inventory/audit/*` | audit:* | audit.urls |
| `/inventory/reports/*` | reports:* | reports.urls |
| `/inventory/procurement/*` | procurement:* | procurement.urls |
| `/telescope/*` | telescope:* | telescope.urls |
| `/` (empty) | home | redirect → tasks:dashboard |
| `/media/*` | — | MEDIA_ROOT (DEBUG) |
| `/__debug__/*` | — | debug_toolbar (DEBUG) |

## 7.2 Tasks App — Complete Route List (`tasks/urls.py`)

| Path | Name | View module |
|------|------|-------------|
| `dashboard/` | dashboard | dashboard_views |
| `search/` | global_search | misc_views |
| `projects/` | project_list | project_views |
| `projects/new/` | project_create | project_views |
| `projects/<pk>/` | project_detail | project_views |
| `projects/<pk>/edit/` | project_edit | project_views |
| `projects/<pk>/settings/` | project_settings | project_views |
| `projects/<pk>/tasks/` | project_task_list | project_views |
| `projects/<pk>/requirements/` | project_requirement_list | project_views |
| `projects/<pk>/bugs/` | project_bug_list | project_views |
| `projects/<pk>/members/` | project_members | project_views |
| `projects/<pk>/delete/` | project_delete | project_views |
| `projects/<pk>/archive/` | project_archive | project_views |
| `projects/<pk>/request-release/` | project_request_release | project_views |
| `projects/<pk>/approve-release/` | project_approve_release | project_views |
| `projects/<pk>/cicd/` | project_cicd | release_views |
| `projects/<pk>/requirements/bulk/` | requirement_bulk_create | release_views |
| `projects/<pk>/requirements/new/` | requirement_create | release_views |
| `requirements/<pk>/` | requirement_detail | release_views |
| `requirements/<pk>/edit/` | requirement_edit | release_views |
| `requirements/<pk>/delete/` | requirement_delete | release_views |
| `requirements/<pk>/approve/` | requirement_approve | release_views |
| `requirements/<pk>/restore/` | requirement_restore | misc_views |
| `requirements/<pk>/permanent-delete/` | requirement_permanent_delete | misc_views |
| `projects/<pk>/requirements/report/` | requirement_report | release_views |
| `projects/<pk>/modules/` | module_list | module_views |
| `projects/<pk>/modules/new/` | module_create | module_views |
| `modules/<pk>/` | module_detail | module_views |
| `modules/<pk>/edit/` | module_edit | module_views |
| `modules/<pk>/delete/` | module_delete | module_views |
| `modules/<pk>/members/` | module_members | module_views |
| `projects/<pk>/releases/` | release_list | release_views |
| `projects/<pk>/releases/new/` | release_create | release_views |
| `releases/new/` | release_create_no_project | release_views |
| `releases/<pk>/` | release_detail | release_views |
| `releases/<pk>/edit/` | release_edit | release_views |
| `releases/<pk>/delete/` | release_delete | release_views |
| `releases/<pk>/download/` | release_download | release_views |
| `releases/<pk>/assets/download/` | release_assets_download | release_views |
| `releases/assets/<pk>/download/` | release_asset_download | release_views |
| `releases/<pk>/compare/` | release_compare | release_views |
| `releases/<pk>/restore/` | release_restore | release_views |
| `releases/<pk>/publish/` | release_publish | release_views |
| `releases/<pk>/assets/upload/` | release_asset_upload | release_views |
| `releases/<pk>/delete-request/` | release_deletion_request | release_views |
| `releases/admin/deletion-requests/` | admin_deletion_requests | release_views |
| `releases/admin/deletion-resolve/<pk>/` | resolve_deletion_request | release_views |
| `releases/` | global_release_list | release_views |
| `knowledge-base/` | kb_overview | notes.views |
| `knowledge-base/new/` | kb_create_global | notes.views |
| `projects/<pk>/knowledge-base/` | kb_list | notes.views |
| `projects/<pk>/knowledge-base/new/` | kb_create | notes.views |
| `knowledge-base/<pk>/` | kb_detail | notes.views |
| `knowledge-base/<pk>/edit/` | kb_edit | notes.views |
| `knowledge-base/<pk>/access/` | kb_access | notes.views |
| `knowledge-base/<pk>/delete/` | kb_delete | notes.views |
| `knowledge-base/<pk>/restore/` | note_restore | misc_views |
| `knowledge-base/<pk>/permanent-delete/` | note_permanent_delete | misc_views |
| `tasks/` | task_list | task_views |
| `projects/<pk>/tasks/bulk/` | task_bulk_create | task_views |
| `ajax/get-project-data/` | get_project_data | task_views |
| `tasks/new/` | task_create | task_views |
| `tasks/<pk>/` | task_detail | task_views |
| `tasks/<pk>/edit/` | task_edit | task_views |
| `tasks/<pk>/delete/` | task_delete | task_views |
| `tasks/<pk>/approve/` | task_approve | task_views |
| `tasks/<pk>/restore/` | task_restore | misc_views |
| `tasks/<pk>/permanent-delete/` | task_permanent_delete | misc_views |
| `tasks/<pk>/status/` | task_update_status | task_views |
| `projects/<pk>/tasks/report/` | task_report | release_views |
| `notifications/` | notifications | notifications.views |
| `notifications/<pk>/read/` | notification_read | notifications.views |
| `bugs/` | bug_list | bugs.views |
| `bugs/new/` | bug_create | bugs.views |
| `bugs/<pk>/` | bug_detail | bugs.views |
| `bugs/<pk>/edit/` | bug_edit | bugs.views |
| `bugs/<pk>/comment/` | bug_comment_add | bugs.views |
| `bugs/<pk>/resolve/` | bug_resolve | bugs.views |
| `bugs/<pk>/delete/` | bug_delete | bugs.views |
| `bugs/<pk>/restore/` | bug_restore | misc_views |
| `bugs/<pk>/permanent-delete/` | bug_permanent_delete | misc_views |
| `projects/<id>/test-cases/new/` | test_case_create | testcases.views |
| `projects/<id>/test-cases/bulk/` | project_test_case_bulk_create | testcases.views |
| `test-cases/<pk>/` | test_case_detail | testcases.views |
| `test-cases/<pk>/edit/` | test_case_edit | testcases.views |
| `test-cases/<pk>/delete/` | test_case_delete | testcases.views |
| `test-cases/<pk>/restore/` | test_case_restore | misc_views |
| `test-cases/<pk>/permanent-delete/` | test_case_permanent_delete | misc_views |
| `test-cases/<pk>/verify/` | test_case_verify | testcases.views |
| `calendar/` | calendar | events.views |
| `calendar/google/init/` | google_calendar_init | events.views |
| `calendar/google/callback/` | google_calendar_callback | events.views |
| `calendar/toggle-caldav-sync/` | toggle_caldav_sync | events.views |
| `calendar/event/new/` | event_create | events.views |
| `calendar/event/<pk>/` | event_detail | events.views |
| `calendar/event/<pk>/edit/` | event_edit | events.views |
| `calendar/event/<pk>/delete/` | event_delete | events.views |
| `api/tasks-for-project/` | tasks_for_project | api.endpoints |
| `api/project-modules/` | project_modules_api | api.endpoints |
| `api/project-requirements/` | project_requirements_api | api.endpoints |
| `api/project-members/` | project_members_api | api.endpoints |
| `reports/` | reports | report_views |
| `report-center/` | report_center | report_views |
| `projects/<pk>/report-center/` | project_report_center | report_views |
| `projects/<pk>/master-report/` | master_report | report_views |
| `rtm/<pk>/` | rtm_view | release_views |
| `test-report/<pk>/` | test_case_report | release_views |
| `audit-logs/` | audit_log_list | audit_views |
| `trash/` | trash | misc_views |
| `folders/<pk>/restore/` | category_restore | misc_views |
| `folders/<pk>/permanent-delete/` | category_permanent_delete | misc_views |
| `pm-inventory/` | inventory_list | misc_views |
| `projects/<id>/document/<doc_id>/discussion/` | document_discussion | files.detail_views |
| `projects/<id>/folder/<folder_id>/discussion/` | folder_discussion | files.detail_views |

## 7.3 Files App Routes (`/files/`)

| Path | Name |
|------|------|
| `` | file_list |
| `upload/` | file_upload |
| `<pk>/` | file_detail |
| `<pk>/download/` | file_download |
| `<pk>/view/` | file_view |
| `<pk>/edit/` | file_edit |
| `<pk>/content-edit/` | file_content_edit |
| `<pk>/delete/` | file_delete |
| `<pk>/restore/` | file_restore |
| `<pk>/permanent-delete/` | file_permanent_delete |
| `<pk>/hide-from-trash/` | file_hide_from_trash |
| `<pk>/access/` | file_access |
| `project/<pk>/` | project_files |
| `project/<pk>/categories/new/` | category_create |
| `api/project-categories/` | project_categories_api |
| `settings/` | system_settings |
| `categories/<pk>/delete/` | category_delete |
| `categories/<pk>/edit/` | category_edit |
| `categories/<pk>/download/` | download_folder |
| `move-item/` | move_item |
| `manage-resource/` | manage_resource |
| `audit-logs/` | file_audit_logs |

## 7.4 Chat Routes (`/chat/` + WebSocket)

| Path | Type | Name |
|------|------|------|
| `` / `home/` | HTTP | chat_home |
| `project/<project_id>/` | HTTP | project_chat |
| `api/messages/<room_id>/` | HTTP | api_messages |
| `create-group/` | HTTP | create_group |
| `api/search/` | HTTP | search_messages |
| `api/upload/` | HTTP | upload_chat_file |
| `api/clear/<room_id>/` | HTTP | clear_chat |
| `api/quick-chat-list/` | HTTP | api_quick_chat_list |
| `api/forward/` | HTTP | forward_message |
| `api/bulk-delete/` | HTTP | bulk_delete_messages |
| `ws/chat/<room_id>/` | WebSocket | ChatConsumer |
| `ws/notifications/` | WebSocket | NotificationConsumer |

## 7.5 Inventory Routes Summary

| Prefix | Key endpoints |
|--------|---------------|
| `/inventory/dashboard/` | dashboard-page, overview, api |
| `/inventory/main/` | superadmin/branch dashboards, adjustments, serials, limits, alerts, rentals, shortage, users, settings, notifications |
| `/inventory/products/` | products CRUD, categories, api, excel template |
| `/inventory/stock/` | stock-in, stock-out, transfer, receive, apis, templates |
| `/inventory/audit/` | audit-logs |
| `/inventory/reports/` | statistics, export excel/csv/pdf |
| `/inventory/procurement/` | upload, restock, send-all-alerts, template |

---

# 8. Forms & Validation Reference

| Form | App | Model | Key fields / rules |
|------|-----|-------|-------------------|
| `LoginForm` | accounts | — | Username/password; AuthenticationForm subclass |
| `UserCreateForm` | accounts | User | role, team, all permission flags |
| `UserEditForm` | accounts | User | Same; excludes password |
| `UserSelfPasswordChangeForm` | accounts | User | Old + new password validators |
| `ProjectForm` | tasks | Project | name, module, dates, managers, members |
| `TaskForm` | tasks | Task | assignees, module, requirement, release, sprint |
| `RequirementForm` | tasks | Release forms | type, status, dependencies |
| `ReleaseForm` | tasks | Release | version, tag, release_type |
| `BugReportForm` | bugs | BugReport | project-scoped assignee queryset |
| `BugCommentForm` | bugs | BugComment | content, attachment |
| `BugResolutionForm` | bugs | BugReport | resolution fields |
| `TestCaseForm` | testcases | TestCase | steps, expected, assignees |
| `KnowledgeBaseNoteForm` | notes | KnowledgeBaseNote | markdown content |
| `CalendarEventForm` | events | CalendarEvent | datetime range, attendees |
| `BudgetForm` | finance | Budget | total_amount |
| `ExpenseForm` | finance | Expense | amount, category, receipt FK |
| `ProjectFileUploadForm` | files | ProjectFile | multi-file, category, project |
| `ProductForm` | products | Product | branch-aware rack/shelf |

**Password validators (global):** UserAttributeSimilarity, MinimumLength, CommonPassword, NumericPassword.

---

# 9. Templates & Static Assets Inventory

## 9.1 Global layouts

| Template | Purpose |
|----------|---------|
| `templates/base.html` | PM sidebar layout |
| `templates/core_base.html` | Alternate core wrapper |
| `templates/inventory_base.html` | Inventory subsystem layout |

## 9.2 PM templates by app

| Directory | Files (representative) |
|-----------|------------------------|
| `templates/accounts/` | login, user_list, user_form, profile, settings |
| `templates/tasks/` | dashboard, admin_dashboard, task_*, trash |
| `templates/projects/` | project_list, detail, form, members, settings |
| `templates/modules/` | module_list, detail, form |
| `templates/releases/` | release_list, detail, form, compare |
| `templates/bugs/` | bug_list, detail, form |
| `templates/kb/` | kb_overview, list, detail, form, access |
| `templates/calendar/` | calendar, event_form, event_detail |
| `templates/test_cases/` | bulk_form, form, detail, verify |
| `templates/notifications/` | notifications.html |
| `templates/files/` | file_list, project_files, detail, upload, discussion |
| `templates/finance/` | project_expenses, expense_form, budget_form |
| `templates/telescope/` | dashboard, detail, form, base |
| `templates/reports/` | reports, report_center, master_report |
| `templates/audit/` | audit_log_list |
| `templates/search/` | search_results |

## 9.3 Chat templates (app-local)

`chat/templates/chat/main_chat.html`, `create_group.html`, `chat_popup.html`

## 9.4 Static assets (`static/`)

CSS themes, Kanban JS, calendar helpers, file preview scripts, Chart.js integration (CDN in templates).

---

# 10. Business Logic Flowcharts (All Modules)

## 10.1 Project creation (end-to-end)

```
[User: project_create POST]
    → Validate ProjectForm
    → Project.save() → auto project_id
    → ProjectService.initialize_project_folders()
         → FileCategory tree + README.md
    → chat.signals: ChatRoom(project) + participants
    → ProjectService.notify_project_assignment()
    → tasks.signals: AuditLog create
    → Redirect project_detail
```

## 10.2 Release publish (end-to-end)

```
[User: release_publish POST]
    → ReleaseService.create_release_snapshot()
         → FOR each latest ProjectFile:
              SHA-256 hash → copy bytes → ReleaseFile row
    → ReleaseService.publish_release()
         → status=completed, published_at
         → sync_release_to_project_resources() + ZIP bundle
         → ReleaseLog 'published'
    → Release.is_locked = True (no further edits)
```

## 10.3 Bug → Task linkage

```
[User: bug_create with assignees]
    → BugReport.save()
    → NOTIFY managers (bug_reported)
    → Task.create(type=bug, linked implicitly via title)
    → task.assignees = bug.assignees
    → NOTIFY assignees (task_assigned)
[User: bug_resolve]
    → IF linked_task → status=done
```

## 10.4 Inventory stock movement

```
[Stock In POST]
    → StockEntry(entry_type=in)
    → signal → recalculate_branch_stock()
    → AuditLog.log()
    → InventoryNotification (if non-admin)

[Stock Transfer CREATE]
    → StockEntry OUT at source (immediate)
    → status=pending

[Transfer RECEIVE POST]
    → StockEntry IN at destination
    → Update rack/shelf on BranchStock
    → status=received
```

## 10.5 File upload with versioning

```
[file_upload POST multipart]
    → FOR each file:
         IF same name exists in category (latest):
            new version = old.version + 1, parent_file=old
         ELSE version=1
         → detect_file_type(extension)
         → save to media/projects/PRJ-ID/.../file
    → AuditLog upload (if wired in view)
```

> **Full per-function pseudocode** for all 200+ view functions: see `PROJECT_REPORT_CODE_ENCYCLOPEDIA.md`.

---

# 11. Services, Signals & Background Jobs

## 11.1 Service classes

| Service | File | Methods |
|---------|------|---------|
| `ProjectService` | `tasks/services/project_service.py` | `initialize_project_folders`, `notify_project_assignment`, `handle_deletion_request` |
| `ReleaseService` | `tasks/services/release_service.py` | `calculate_hash`, `create_release_snapshot`, `publish_release`, `sync_release_to_project_resources` |
| `NotificationService` | `tasks/services/notification_service.py` | `create_notification` (+ WebSocket push) |
| `ReportEngine` | `tasks/services/report_engine.py` | Master report MD/PDF/DOCX/XLSX generation |
| `KBService` | `notes/services.py` | `save_note_as_file` |

## 11.2 All Django signals (project-wide)

| Sender | Signal | Handler | App |
|--------|--------|---------|-----|
| User | post_save | create_user_presence | chat |
| Project | post_save | create_project_chat_room | chat |
| Project.members | m2m_changed | update_project_chat_participants | chat |
| ChatAttachment | post_delete | auto_delete_file_on_delete | chat |
| User | logged_in/out | audit login/logout | tasks |
| Project, Requirement, Task, TestCase, Bug, Release | post_save | audit_post_save | tasks |
| Same | post_delete | audit_post_delete | tasks |
| Task.assignees | m2m_changed | add_task_assignees_to_module | tasks |
| Task | post_save | add_task_module_members | tasks |
| StockEntry | pre_save/post_save/post_delete | recalculate stock | inventory |
| InventoryAdjustment | pre_save/post_save/post_delete | recalculate stock | inventory |

## 11.3 Management commands

| Command | App | Purpose |
|---------|-----|---------|
| `seed_data` | tasks | Demo users, projects, tasks |
| `check_alerts` | inventory | Generate stock alerts |
| `recalculate_stock` | inventory | Bulk BranchStock recalc |
| `sync_serials` | inventory | Serial number sync |
| `create_sample_*_excel` | stock/products/procurement | Sample import templates |

---

# 12. Model Field Reference (All Tables)

## 12.1 PM domain (`tasks` app tables)

### Project
`project_id`, `name`, `description`, `module`, `status`, `priority`, `visibility`, `background_color`, `button_color`, `start_date`, `end_date`, `created_by_id`, `project_incharge_id`, `progress`, `deletion_requested_*`, `is_archived`, `is_released`, `release_requested*`, `image`, timestamps.

### Task
`task_id`, `title`, `description`, `project_id`, `requirement_id`, `module_id`, `release_id`, `task_type`, `status`, `priority`, `parent_task_id`, `sprint_id`, `milestone`, `story_points`, `due_date`, `deadline`, `estimated_hours`, `actual_hours`, `tags`, `order`, `is_approved`, `is_in_trash`, `deleted_*`, `completed_at`.

### Requirement
`req_id`, `name`, `description`, `requirement_type`, `priority`, `status`, `assigned_team`, `version`, `is_approved`, `is_in_trash`, M2M `dependencies`.

### Release / ReleaseFile
Release: `name`, `release_type`, `status`, `version`, `tag_name`, `is_draft`, `is_prerelease`, `checksum`, `metadata`, `published_*`.  
ReleaseFile: `file`, `original_name`, `relative_path`, `content_hash`, `version`, `is_extra_asset`.

### AuditLog (PM)
`user_id`, `action_type`, `module`, `entity_id`, `entity_name`, `old_value` (JSON), `new_value` (JSON), `details`, `ip_address`, `user_agent`, `timestamp`.

## 12.2 Sibling PM apps (separate tables)

| Table | Model | Key FKs |
|-------|-------|---------|
| `tasks_bugreport` | BugReport | project, reported_by, linked_task |
| `tasks_bugcomment` | BugComment | bug, parent |
| `tasks_testcase` | TestCase | project, task |
| `tasks_knowledgebasenote` | KnowledgeBaseNote | project, module |
| `tasks_notification` | Notification | recipient, task, project, test_case |
| `tasks_calendarevent` | CalendarEvent | project, task |
| `files_*` | ProjectFile, FileCategory, etc. | project, category, parent_file |
| `finance_*` | Budget, Expense | project, receipt→ProjectFile |
| `chat_*` | ChatRoom, Message, etc. | room UUID, participants M2M |
| `telescope_telescope` | Telescope | — |

## 12.3 Inventory domain

| Model | Primary keys / uniqueness |
|-------|-------------------------|
| Branch | `code` unique |
| BranchStock | unique `(branch, product)` |
| Product | `serial_number` unique nullable |
| SerialNumber | `serial_number` unique |
| InventoryUser | `username` unique |
| ProcurementRequest | — |
| StockEntry / StockTransfer | — |
| audit.AuditLog | — |

---

**End of Document**

*This report (v2.0) documents the full IIAP OM platform. For line-by-line view logic and pseudocode of every function, read **`project_documentation/PROJECT_REPORT_CODE_ENCYCLOPEDIA.md`** alongside this file.*

