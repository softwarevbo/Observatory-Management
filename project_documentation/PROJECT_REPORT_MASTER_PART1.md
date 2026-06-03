# IIAP OM — Master Technical Report (Part 1 of 3)

**Document Class:** Enterprise Architecture & Implementation Dossier  
**Target Length:** ~100 pages (combined Parts 1–3)  
**Version:** 3.0 Master Edition  
**Date:** May 29, 2026  

---

\newpage

## Document Map

| Part | Chapters | File |
|------|----------|------|
| **Part 1** | I–VI: Introduction, Platform, Accounts, PM Core, Projects, Tasks | This file |
| **Part 2** | VII–XII: QA, Files, Finance, Calendar, Chat, Telescope | `PROJECT_REPORT_MASTER_PART2.md` |
| **Part 3** | XIII–XVIII: Inventory, Architecture, Security, Ops, Glossary | `PROJECT_REPORT_MASTER_PART3.md` |

**Companion references:** `PROJECT_REPORT.md` (summary), `PROJECT_REPORT_CODE_ENCYCLOPEDIA.md` (function index)

---

# CHAPTER I — INTRODUCTION & EXECUTIVE NARRATIVE

## I.1 Purpose of This Document

This master report exists to provide a **single, authoritative narrative** of the IIAP OM (Indian Institute of Astrophysics Project Management) platform. Unlike a README or API reference, it explains not only *what* the system does but *how* each layer cooperates: from the moment a researcher logs in, through project creation, requirement traceability, test-gated task completion, immutable release publication, real-time chat, branch-level inventory movements, and observatory telescope monitoring.

The platform was engineered as a **Django monolith** with optional **ASGI/WebSocket** channels rather than as a distributed microservice mesh. That architectural choice reduces operational complexity for institute deployments while concentrating business rules in the ORM, server-rendered views, and a small set of service classes. Every major workflow in this document is accompanied by diagrams, decision tables, and prose suitable for onboarding engineers, writing academic theses, or preparing audit submissions.

## I.2 Organizational Context

IIAP OM serves multi-disciplinary engineering teams spanning **Electronics, Mechanical, Optics, Simulation, and Software**. Projects are not generic “tickets”; they carry module affinity, formal requirements (BRD/FRD/TRD), linked test cases, release baselines, and financial budgets. The same installation also hosts a **physically separate inventory domain** (branches, serial numbers, procurement) and a **telescope operations dashboard** aligned with VBO observatory instruments (VBT, JCBT, Zeiss, Cassegrain, Schmidt).

The design assumption is that **one institute** runs one deployment, with role separation enforced in software rather than by spinning up separate products.

## I.3 High-Level Capability Matrix

| Capability Domain | Primary Apps | User-facing entry |
|-------------------|--------------|-------------------|
| Identity & access | accounts | `/accounts/login/` |
| Project lifecycle | tasks | `/dashboard/`, `/projects/` |
| Quality assurance | testcases, bugs | `/test-cases/`, `/bugs/` |
| Documentation | files, notes | `/files/`, `/knowledge-base/` |
| Collaboration | chat, notifications | `/chat/`, bell icon |
| Planning | events | `/calendar/` |
| Financial control | finance | `/finance/project/<id>/` |
| Observatory | telescope | `/telescope/` |
| Supply chain | inventory, products, stock, procurement | `/inventory/dashboard/` |

## I.4 Platform Architecture (Narrative)

At runtime, the browser speaks HTTP to Django and, for chat, WebSocket to Daphne. Django’s middleware stack authenticates the session, applies CSRF protection, and—for inventory URLs—may **substitute** `request.user` with an `InventoryUser` instance loaded from `session['inv_user_id']`. Views are overwhelmingly **function-based**, render HTML templates, and mutate the SQLite (or PostgreSQL) database through the ORM. Side effects propagate through **Django signals**: audit rows, stock recalculation, chat room creation, and automatic project membership updates.

```
                    ┌─────────────────────────────────────────┐
                    │           PRESENTATION TIER              │
                    │  Templates + Vanilla JS + Chart.js      │
                    │  FullCalendar + WebSocket client        │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │         APPLICATION TIER (Django)        │
                    │  Views │ Forms │ Decorators │ Services   │
                    │  Signals │ Context Processors │ Channels  │
                    └────────────────────┬────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
│  DOMAIN MODEL   │            │  FILE STORAGE   │            │  EXTERNAL APIs  │
│  ORM / SQLite   │            │  MEDIA_ROOT     │            │  Google Cal     │
│  40+ models     │            │  /media/...     │            │  CalDAV/Radicale │
└─────────────────┘            └─────────────────┘            └─────────────────┘
```

## I.5 Technology Stack (Extended)

**Django 4.2** provides admin, sessions, authentication hooks, and migrations. **Channels + Daphne** multiplex HTTP and WebSocket on one port. The front end deliberately avoids React/Vue: **server-rendered HTML** with a dark theme (Space Grotesk, DM Sans) keeps the codebase approachable for institute IT staff. **Chart.js** powers analytics; **FullCalendar** renders schedules. Report exports use **openpyxl**, **xhtml2pdf**, and **python-docx** via `tasks/services/report_engine.py`.

Production hardening requires PostgreSQL, Redis channel layers, HTTPS, and removal of debug tooling—documented in Part 3.

## I.6 Document Conventions

- **Diagrams:** ASCII for universal rendering; Mermaid where noted in web viewers.
- **Roles:** Admin, Project Manager (PM), Member, Student; plus Inventory roles Super Admin, Branch Admin, Staff.
- **IDs:** Auto-generated identifiers (e.g. `PRJ-S-2026-0021`) are first-class UX elements.

---

# CHAPTER II — CORE PLATFORM (`core`)

## II.1 Configuration Philosophy

The `core` package is the spine of the installation. `settings.py` declares eighteen custom applications alongside Django contrib and infrastructure packages (`daphne`, `channels`, `debug_toolbar`). Critical globals include `AUTH_USER_MODEL = 'accounts.User'`, `TIME_ZONE = 'Asia/Kolkata'`, and generous upload limits (`DATA_UPLOAD_MAX_MEMORY_SIZE` = 10 GB) suited to engineering CAD archives and release bundles.

`SESSION_EXPIRE_AT_BROWSER_CLOSE = True` reduces session hijack risk on shared lab machines—a common scenario at research institutes. `ALLOWED_HOSTS = ["*"]` and `DEBUG = True` in the repository copy are **development defaults** and must be tightened before any public deployment.

## II.2 ASGI vs WSGI

`core/asgi.py` registers `ProtocolTypeRouter`: HTTP traffic uses standard Django ASGI; WebSocket traffic routes through `AuthMiddlewareStack` to `chat.routing.websocket_urlpatterns`. This means chat works only when the process manager launches Daphne (or uvicorn with equivalent routing)—`runserver` supports ASGI in modern Django, but production typically uses:

```bash
daphne -b 0.0.0.0 -p 8001 core.asgi:application
```

## II.3 URL Mounting Strategy

`core/urls.py` deliberately mounts **tasks at root** (`path("", include("tasks.urls"))`) so PM URLs are short (`/dashboard/`, `/projects/`). Inventory is namespaced under `/inventory/*` to simplify middleware matching. Files and finance have dedicated prefixes. The home route redirects anonymous visitors to login indirectly via dashboard redirect.

## II.4 Context Processors (Global UI State)

Every PM template receives:

| Processor | Injects | Purpose |
|-----------|---------|---------|
| `system_settings` | `sys_settings` | Theme colors, font size |
| `notifications_count` | `unread_count` | Navbar badge |
| `notes_count` | `notes_count` | KB sidebar indicator |
| `sidebar_projects` | `sidebar_projects` | Quick project navigation |
| `inventory_notifications_count` | (inventory base) | Stock alerts |

This pattern avoids repeating queries in dozens of views.

---

# CHAPTER III — ACCOUNTS & IDENTITY (`accounts`)

## III.1 Narrative Overview

The accounts application implements a **rich custom User model** rather than stock Django users. Each person carries a **role** (admin, project_manager, member, student), an engineering **team/module** affiliation, and dozens of boolean capability flags spanning PM, inventory, and telescope domains. Authentication is **session-based**: successful login sets `sessionid` cookie; no JWT is issued for browser PM flows.

A parallel identity system exists for warehouse staff: **`InventoryUser`** lives in the inventory app but authenticates through `accounts.views.inventory_login`, which stores only `inv_user_id` in session. The `InventoryAccessMiddleware` can promote that identity to `request.user` on inventory paths while **blocking** inventory-only users from PM screens—a hard isolation boundary.

## III.2 User Model — Field-by-Field Semantics

**Profile fields** (`nickname`, `designation`, `phone`, `profile_picture`, `avatar_color`) support HR-style directory displays and chat avatars. **Access flags** gate top-level products: `can_access_pm`, `can_access_inventory`, `can_access_telescope`, `is_telescope_admin`. **Telescope operation flags** (`can_operate_vbt`, `can_command_dome`, `can_trigger_exposures`, etc.) fine-tune who may act on instrument UI controls (extensible to future live control integrations).

**Inventory compatibility flags** mirror `InventoryUser` permissions so a single PM user with `can_access_inventory` can browse stock without a second login.

## III.3 Login Flow (Complete)

```
┌──────────┐    POST credentials     ┌─────────────┐
│  Browser │ ───────────────────────►│ login_view  │
└──────────┘                         └──────┬──────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
             ┌────────────┐         ┌────────────┐         ┌────────────┐
             │ Inactive?  │         │ No PM flag │         │ Valid user │
             │ Show error │         │ Show error │         │ login()    │
             └────────────┘         └────────────┘         └─────┬──────┘
                                                                │
                    Clear inv_user_id from session ◄────────────┘
                    Redirect to dashboard or ?next=
```

**Paragraph detail:** When `can_access_pm` is false and the user is not a superuser, the system refuses PM entry even if credentials are valid—this supports inventory-only or telescope-only accounts that share the same username namespace. Deactivated users (`is_active=False`) receive an explicit message to contact an administrator rather than a generic failure, aiding helpdesk workflows.

## III.4 User Management Workflows

Administrators access `/accounts/users/` with tabs for **PM users**, **inventory users**, and **telescope users**. Creation forms expose the full permission matrix. **Toggle active** and **reset password** are exposed as separate views to avoid accidental lockouts. **Role change** via AJAX (`change_user_role`) allows quick promotion to project_manager without re-entering profile data.

Telescope user provisioning sets `can_access_pm=False`, `can_access_inventory=False`, `can_access_telescope=True`, ensuring observatory operators land on `/telescope/` after `telescope_login`.

## III.5 Middleware Deep Dive

`InventoryAccessMiddleware` is among the most security-sensitive components. For paths starting with `/inventory/`, it enforces:

1. **Authentication** via inventory session or PM user with inventory flag.
2. **Page-level ACL** for adjustments, serials, limits, alerts, rentals, shortage exports.
3. **POST vs GET** distinction: viewing a page requires `can_access_*`; submitting forms requires `can_manage_*`.

For inventory-pure sessions, any attempt to open `/dashboard/` redirects to `/inventory/dashboard/`, preventing accidental data leakage across domains.

## III.6 Security Considerations (Accounts)

| Threat | Mitigation |
|--------|------------|
| Session fixation | Django session rotation on login |
| Cross-domain user confusion | Separate inventory session key |
| Privilege escalation | Decorators on sensitive views; admin-only user CRUD |
| Password quality | Django validators in `AUTH_PASSWORD_VALIDATORS` |

---

# CHAPTER IV — PROJECT MANAGEMENT CORE (`tasks`)

## IV.1 Narrative Overview

The `tasks` application is the **largest codebase segment** (~42 Python modules excluding migrations). It owns the dashboard, projects, requirements, modules, tasks, sprints, releases, CI/CD metadata, PM audit logs, trash/recycle bin, global search, report center, and—critically—**mounts URL routes** for bugs, test cases, notes, calendar, and notifications under the `tasks:` template namespace.

This “hub app” pattern means templates reference `{% url 'tasks:bug_list' %}` even though `BugReport` lives in `bugs.models`. Legacy database table names (`tasks_bugreport`) reflect an earlier monolith split.

## IV.2 Domain Model Relationships (Prose)

A **Project** is the root aggregate. It spawns **ProjectModules** (sub-teams), **Requirements** (traceable specs), **Tasks** (work units), **Releases** (baselines), and indirectly **Files**, **Bugs**, **TestCases**, and **ChatRooms**. Progress on the project is not manually set—it is **computed** from child task statuses and test-case pass rates whenever tasks save.

**Requirements** support versioning through `RequirementVersion` rows capturing historical snapshots on change. **Tasks** may nest via `parent_task`, belong to a **Sprint**, and link to a **Release** for cut-line planning. **Comments** on tasks support threading through `parent` FK and file attachments.

## IV.3 Project Lifecycle — Full Flow

```
 PLANNING ──► ACTIVE ──► ON_HOLD ──► COMPLETED
                  │                      │
                  └──────► CANCELLED     └──► ARCHIVED (is_archived flag)
                  
 RELEASE REQUEST ──► ADMIN APPROVE ──► is_released=True
 DELETION REQUEST (dual: admin + PM flags) ──► DELETE
```

### IV.3.1 Project Creation (Step-by-Step)

When a project manager submits **Create Project**:

1. `ProjectForm` validates name, module, dates, managers, members, optional image, optional initial budget.
2. `project.created_by = request.user`; `project.save()` triggers **ID generation** (`PRJ-{initials}-{year}-{seq}`).
3. M2M fields `managers` and `members` persist via `form.save_m2m()`.
4. If budget amount provided, `finance.Budget` row is created.
5. `ProjectService.initialize_project_folders()` builds the **file taxonomy** (resources/notes, requirements/specifications, test_management, releases) and seeds `README.md` as a public `ProjectFile`.
6. `chat.signals.create_project_chat_room` fires, creating a **project chat room** with creator and managers as participants.
7. `ProjectService.notify_project_assignment()` emails in-app notifications to managers and members.
8. `tasks.signals.audit_post_save` writes PM **AuditLog** row.
9. User redirects to `project_detail`.

**Paragraph:** The folder initialization step is essential for user experience: without it, the Files tab would be empty and releases would lack a canonical directory. The README auto-file gives new members immediate context inside the document browser.

### IV.3.2 Project Detail Hub

`project_detail` aggregates: recent tasks (excluding bug-type tasks from main list), requirement stats, file previews, bug counts, module cards, and progress bar. Access requires membership, management, incharge, or admin—others receive an error flash and redirect.

### IV.3.3 Dual-Flag Deletion

Project deletion is a **two-key safety** mechanism. An admin sets `deletion_requested_by_admin`; a managing PM sets `deletion_requested_by_pm`. Only when **both** are true (or a superuser forces delete) does permanent removal proceed. Cancelling either flag resets the workflow. Notifications inform the counterpart role when one party requests deletion—documented in `ProjectService.handle_deletion_request`.

## IV.4 Progress Calculation (Mathematical Narrative)

Each non-trash task contributes a weight between 0 and 100. Status alone maps to 0 (todo/blocked), 30 (in_progress), 80 (review), or 100 (done). When test cases exist, the weight becomes a **convex combination**: 60% status weight plus 40% pass percentage. The project progress is the arithmetic mean across tasks. This design incentivizes teams to maintain test coverage: a task marked “done” with failing tests still drags progress downward if test cases are linked.

## IV.4.1 Progress Formula Diagram

```
                    ┌─────────────────────────────────┐
                    │         For each Task T          │
                    └─────────────────┬───────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
    ┌──────────────────┐                          ┌──────────────────┐
    │ Status weight Ws │                          │ TC pass rate Wt  │
    │ todo: 0            │                          │ passed/total %   │
    │ in_progress: 30    │                          └────────┬─────────┘
    │ review: 80         │                                   │
    │ done: 100          │         ┌──────────────────────────┘
    └─────────┬──────────┘         │
              │            ┌───────▼────────┐
              └───────────►│ If TC count>0: │
                           │ W = 0.6*Ws +   │
                           │     0.4*Wt     │
                           │ Else: W = Ws   │
                           └───────┬────────┘
                                   ▼
                    Project.progress = mean(W) over all tasks
```

## IV.5 Dashboard Experiences

### IV.5.1 Administrator Dashboard

Admins see `admin_dashboard.html` with institute-wide KPIs: total projects, active projects, user count, SQLite database size on disk, and count of projects awaiting **dual deletion approval** (exactly one flag set). This surfaces operational hygiene issues without running SQL manually.

### IV.5.2 PM / Member Dashboard

Non-admins see personalized KPIs: assigned open tasks, overdue and due-today lists computed in Python from queryset iteration, open bug count, five most recent bugs, and five unread notifications. Projects listed exclude archived unless filtered.

## IV.6 Modules & Forum

`ProjectModule` subdivides large efforts (e.g. “Optics Design”, “Firmware”). `ModuleMember` assigns designer/developer/tester roles. `module_detail` includes a **forum** (`ModuleForumPost`) for threaded discussions scoped to the module—distinct from project-level chat.

## IV.7 Requirements Engineering

Requirements carry `requirement_type` (business, functional, technical, UI/UX, security, API, database, non-functional), `status` (draft through verified), and M2M **dependencies** between requirements for traceability. Approval sets `is_approved=True`, gating visibility in AJAX APIs. Bulk creation accepts spreadsheet-style pasting for migration from legacy documents.

The **RTM view** (`rtm_view`) renders a Requirements Traceability Matrix linking requirements → tasks → test cases—essential for audit presentations.

## IV.8 Release & CI/CD Domain

### IV.8.1 Release Types

- **Partial releases** model minor/nightly drops.
- **Phase releases** model major milestones.

Each release has `version`, `tag_name`, `description` (Markdown release notes), draft/prerelease flags, and optional `checksum` for bundle integrity.

### IV.8.2 Snapshot & Publish Pipeline

`ReleaseService.create_release_snapshot()` iterates latest `ProjectFile` rows (`versions__isnull=True`), computes **SHA-256** per file, copies bytes into `ReleaseFile.file` under `media/releases/<version>/`, and logs to `ReleaseLog`. **Publishing** sets status to `completed`, locks the release (`is_locked` property), syncs assets back into project `Releases/<name>/` category, and may build a ZIP master bundle.

```
  [Draft Release]
        │
        ▼
  Add / select project files ──► create_release_snapshot()
        │                              │
        │                              ▼
        │                    ReleaseFile rows + hashes
        ▼
  release_publish() ──► status=completed, LOCKED
        │
        ├──► sync_release_to_project_resources()
        └──► ReleaseLog 'published'
```

### IV.8.3 PipelineRun

`PipelineRun` records CI status (pending/running/passed/failed) with optional `trigger_commit` hash—integrating with external Git webhooks is a future enhancement, but the schema supports display on `project_cicd` views today.

## IV.9 Trash & Recovery

The unified trash (`misc_views.trash_view`) lists seven entity types. Admins and PMs see all trashed items; members see only items **they** deleted (`deleted_by` FK). Filters support project, deleter, age in days, and text search. Restore views re-check authorization per entity type; permanent delete removes database rows and may unlink media files.

## IV.10 PM Audit System

`tasks.AuditLog` stores structured events: module (project, task, bug, etc.), action_type (create/update/delete/login/...), JSON `old_value`/`new_value` when populated, IP address and user agent on login events. Signals auto-log model saves; file views may log upload/download manually. The viewer at `/audit-logs/` is admin-oriented.

---

# CHAPTER V — TASK EXECUTION (`tasks` / task_views)

## V.1 Narrative Overview

Tasks are the daily work unit. Unlike generic kanban cards, each task carries **typed IDs** (`TAS-`, `BUG-`, `FEA-`, etc.), optional **requirement** and **release** linkage, **approval** gating for member visibility, and **test-case completion** gating for status `done`.

## V.2 Visibility Rules (Member vs PM)

Members see tasks only if `is_approved=True` OR they created the task, AND they are connected to the project (manager, assignee, member, incharge). PMs and admins see broader sets via `get_visible_tasks_qs`. Unapproved tasks allow managers to review before exposing work to junior members—a workflow similar to code review assignment.

## V.3 Task Status API

`task_update_status` accepts JSON POST bodies from Kanban drag-and-drop. Authorization requires manager, incharge, admin, or PM role—not assignees alone (unless they also hold those roles). Attempting `done` when `can_complete` is false returns HTTP 400 with an explicit message about test cases—**the UI should surface this**, and the API enforces it server-side.

When a task enters `review` or `done` and belongs to a release, the view checks whether **all release tasks** are in review/done; if so, it notifies PMs that the release is ready for final review—a coordination shortcut for release managers.

## V.4 Bulk Operations

`task_bulk_create` accepts multiple rows (title, assignee, module) in one POST—useful at sprint planning. `get_project_data` AJAX endpoint returns JSON bundles for dynamic form cascades (modules, requirements, members).

## V.5 Subtasks & Hierarchy

`parent_task` FK enables work breakdown structures. Child tasks inherit project context; progress rollup currently operates at flat task list level per project (subtasks counted as separate tasks in mean progress).

## V.6 Task Comments

`Comment` model supports replies and attachments stored under `media/comments/YYYY/MM/`. Adding a comment triggers notifications to assignees via views (pattern mirrors bug comments).

## V.7 Complete Task State Machine

```
                    ┌─────────┐
         ┌─────────►│  todo   │◄─────────┐
         │          └────┬────┘          │
         │               │               │
         │               ▼               │
         │          ┌─────────┐          │
         │          │ in_prog │          │
         │          └────┬────┘          │
         │               │               │
         │               ▼               │
         │          ┌─────────┐          │
         │    ┌────►│ review  │────┐    │
         │    │     └────┬────┘    │    │
         │    │          │         │    │
         │    │          ▼         │    │
         │    │     ┌─────────┐   │    │
         │    │     │  done   │   │    │
         │    │     └─────────┘   │    │
         │    │  (requires all   │    │
         │    │   TC passed)     │    │
         │    │                  │    │
         │    └──────────────────┘    │
         │                            │
         └──────────┬─────────────────┘
                    ▼
               ┌─────────┐
               │ blocked │ (manual escape hatch)
               └─────────┘
```

---

*End of Part 1 — Continue with Part 2 for Bugs, Test Cases, Files, Finance, Calendar, Chat, Telescope*
