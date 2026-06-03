# IIAP OM — Complete Feature Catalog (Every Feature, Including Mini Features)

**Version:** 1.0  
**Total cataloged features:** 325+  
**Purpose:** Exhaustive inventory for reports, QA checklists, training, and requirements traceability.

---

## How to Use This Document

| Column | Meaning |
|--------|---------|
| **ID** | Unique feature reference (F-###) |
| **Feature** | User-visible capability name |
| **Location** | URL, template, or code file |
| **Description** | What the user sees or what the system does |
| **Access** | Who may use it |

**Roles:** **A**=Admin, **PM**=Project Manager, **M**=Member, **S**=Student, **IC**=Project In-charge, **MM**=Module Member, **All**=any authenticated PM user, **Inv**=Inventory user, **Tel**=Telescope user.

---

# PART A — PLATFORM & AUTHENTICATION

## A.1 Narrative: Identity Layer

IIAP OM separates three portals on one codebase: **Observatory PM**, **Inventory**, and **Telescope**. Each portal has distinct login routes, session keys, and middleware rules. Mini-features such as avatar color fallback, nickname display, and “next URL” redirect after login are easy to overlook but shape daily UX.

## A.2 Feature Table — Accounts & Login

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-001 | PM portal login | `/accounts/login/`, `login.html` | Username/password; themed “Observatory PM” card | All |
| F-002 | Portal theme picker on login | `login.html` `theme-project/inventory/telescope` | Visual switch between three portals before auth | All |
| F-003 | Inventory portal login | `/accounts/inventory_login/` | Separate credential path; sets `inv_user_id` session | Inv |
| F-004 | Telescope portal login | `/accounts/telescope_login/` | Requires `can_access_telescope` | Tel |
| F-005 | Logout | `/accounts/logout/` | Clears session | All |
| F-006 | `?next=` redirect after login | `auth_views.login_view` | Deep-link return post-auth | All |
| F-007 | Deactivated account block | login | Error if `is_active=False` | — |
| F-008 | PM access flag block | login | Error if `can_access_pm=False` (non-superuser) | — |
| F-009 | Clear inventory session on PM login | login | Deletes `inv_user_id` when PM logs in | A/PM/M |
| F-010 | Change password | `/accounts/change-password/` | Self-service password change | All |
| F-011 | Profile page | `/accounts/profile/` | Avatar, stats, recent activity | All |
| F-012 | Settings hub (tabbed) | `/accounts/settings/` | Account, preferences, calendar, issues, system | All |
| F-013 | Profile picture upload | settings #account | ImageField on User | All |
| F-014 | Avatar color picker | settings | Hex color when no photo | All |
| F-015 | Nickname field | settings | Overrides display name in UI | All |
| F-016 | Designation & phone | settings | HR metadata | All |
| F-017 | Light/dark theme preference | settings, `theme_preference` | Per-user UI theme | All |
| F-018 | Email notifications toggle | settings | `email_notifications` (future SMTP) | All |
| F-019 | Report system issue | settings #issues | Creates `SystemIssue` (bug/feature) | All |
| F-020 | View own system issues | settings | List submitted tickets | All |
| F-021 | Admin view all system issues | settings | Institute-wide issue queue | A |
| F-022 | Google Calendar OAuth init | settings + `/calendar/google/init/` | Admin connects Google | A |
| F-023 | Google OAuth callback | `/calendar/google/callback/` | Stores token JSON on user settings | A |
| F-024 | CalDAV URL/user/password fields | settings | Radicale integration config | A |
| F-025 | Toggle CalDAV sync | `/calendar/toggle-caldav-sync/` | Enables two-way sync | A |
| F-026 | Global primary color | settings #system, `SystemSettings` | Admin sets accent `#4f8ef7` style | A |
| F-027 | Global font size | settings | e.g. `14px` default | A |
| F-028 | Default PM password setting | settings | Seed password for new users | A |
| F-029 | User list with pagination | `/accounts/users/` | 10 per page | A |
| F-030 | User search `?q=` | user_list | Filter by name/username | A |
| F-031 | User filter by role | `?role=` | admin/PM/member/student | A |
| F-032 | User filter by team | `?team=` | electronics/mechanical/… | A |
| F-033 | User filter by status | `?status=` | active/inactive | A |
| F-034 | Tab: PM users | `?tab=pm` | Default tab | A |
| F-035 | Tab: Inventory users | `?tab=inventory` | InventoryUser CRUD | A |
| F-036 | Tab: Telescope users | `?tab=telescope` | Tel-flag users | A |
| F-037 | Create PM user | `/accounts/users/create/` | Full permission matrix | A |
| F-038 | User detail view | `/accounts/users/<pk>/` | Read-only profile | A |
| F-039 | Edit user | `/accounts/users/<pk>/edit/` | All flags + team | A |
| F-040 | Reset password (admin) | `.../reset-password/` | Admin sets new password | A |
| F-041 | Delete user | `.../delete/` | Cannot delete self | A |
| F-042 | Toggle active (AJAX/POST) | `.../toggle/` | Enable/disable login | A |
| F-043 | Change role endpoint | `.../change-role/` | POST JSON role update | A |
| F-044 | `can_access_pm` flag | user form | PM portal gate | A |
| F-045 | `can_access_inventory` flag | user form | Inventory routes | A |
| F-046 | `can_access_telescope` flag | user form | Telescope routes | A |
| F-047 | `is_telescope_admin` flag | user form | Tel CRUD | A |
| F-048 | Per-telescope operate flags (7+) | user form | VBT, JCBT, Zeiss, dome, exposures… | A |
| F-049 | Inventory permission mirrors (15+) | user form | adjustments, serials, limits… | A |
| F-050 | Inventory user create/edit/delete/toggle | `/accounts/users/inventory/...` | Separate model | A |
| F-051 | Telescope user create/edit/delete/toggle | `/accounts/users/telescope/...` | Tel provisioning | A |
| F-052 | `display_name` property | User model | nickname → full name → username | System |
| F-053 | `initials` for avatars | User model | Two-letter badge | System |
| F-054 | `inventory_branch` FK on PM user | User model | Hybrid PM+inventory branch | A |

## A.3 Mini-Features — Shell & Navigation

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-055 | PM sidebar navigation | `base.html` | Dashboard, projects, tasks, calendar… | PM users |
| F-056 | Collapsible project tree in sidebar | `base.html` | Per-project sub-links | Project members |
| F-057 | Project button color in tree | `project.button_color` | Custom accent per project | All nav |
| F-058 | Unread notification badge | navbar, context processor | Red count | All |
| F-059 | KB notes count in sidebar | `notes_count` processor | Note indicator | All |
| F-060 | User dropdown menu | `base.html` | Profile, settings, logout | All |
| F-061 | Global chat popup widget | `core_base.html` → `chat_popup.html` | Floating quick-chat | All |
| F-062 | Flash message toasts | `core_base.html` | success/error/info dismiss | All |
| F-063 | Generic modal CSS | `core_base.html` | Overlay dialogs | All PM |
| F-064 | Home redirect `/` → dashboard | `core/urls.py` | Default landing | All |
| F-065 | Django admin site | `/admin/` | Model admin | Staff |
| F-066 | Debug toolbar | `/__debug__/` DEBUG only | SQL/timer panel | Dev |
| F-067 | User avatar partial | `partials/user_avatar.html` | Photo or initials | Templates |
| F-068 | KaTeX/math CSS fix (dark) | `core_base.html` | Renders math in notes | Viewers |

---

# PART B — DASHBOARD & DISCOVERY

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-069 | PM dashboard | `/dashboard/`, `dashboard.html` | Personal KPIs | PM/M/S |
| F-070 | Admin dashboard | `admin_dashboard.html` | DB size, deletion queue | A |
| F-071 | Stat card click-through | dashboard | Links to filtered lists | PM/M |
| F-072 | Overdue tasks list (computed) | dashboard | `due_date < today` | PM/M |
| F-073 | Due today tasks list | dashboard | Exact date match | PM/M |
| F-074 | Open bugs count | dashboard | Non-closed assigned bugs | PM/M |
| F-075 | Recent bugs widget (5) | dashboard | Quick list | PM/M |
| F-076 | Recent notifications (5) | dashboard | Unread preview | PM/M |
| F-077 | Global search | `/search/?q=` | Tasks, projects, files | Scoped |
| F-078 | PM inventory bridge | `/pm-inventory/` | Read-only product qty from PM | All |

---

# PART C — PROJECTS (28+ features)

## C.1 Narrative

Projects are aggregates: every tab (tasks, requirements, resources, bugs, releases) is a **view mode** on one hub. Mini-features include client-side `sortTable`, Kanban column counters via `task_tags.task_count_for_status`, three resource layouts (tree/grid/table), and report modals for SRS/BRD/FRD.

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-079 | Project list | `/projects/` | Paginated 10/page | Scoped |
| F-080 | Filter by engineering module | `?module=` | electronics/mechanical/… | All |
| F-081 | Filter by status | `?status=` | planning/active/… | All |
| F-082 | Filter in-progress pseudo-status | `?status=in_progress` | Excludes completed/cancelled | All |
| F-083 | Show archived projects | `?archived=1` | `is_archived=True` | All |
| F-084 | Filter deletion-requested | `?deletion_requested=` | Pending dual delete | A/PM |
| F-085 | Search projects `?q=` | project_list | Name/description | All |
| F-086 | Auto project ID | `Project.save` | `PRJ-{INIT}-{YEAR}-{####}` | System |
| F-087 | Create project + budget | `/projects/new/` | Optional `Budget` row | A/PM |
| F-088 | Auto folder tree on create | `ProjectService` | 8+ categories + README | System |
| F-089 | Auto project chat room | `chat.signals` | Project-type room | System |
| F-090 | Notify managers/members on create | `ProjectService` | Notifications | System |
| F-091 | Project detail hub | `/projects/<pk>/` | Multi-tab | Members+ |
| F-092 | Tab: requirements | `?view=requirements` | Embedded list | Members+ |
| F-093 | Tab: tasks list | `?view=tasks` or default | Task table | Members+ |
| F-094 | Tab: test cases | project detail | TC summary | Members+ |
| F-095 | Tab: resources | `?view=resources` | File browser | Members+ |
| F-096 | Tab: members | members section | Team display | Members+ |
| F-097 | Kanban view | `?view=kanban` | 5 columns drag status | IC/PM/A |
| F-098 | Kanban column counts | `task_count_for_status` tag | Per-column badge | All |
| F-099 | Client-side table sort | `sortTable()` onclick | No server round-trip | All |
| F-100 | Progress bar (auto) | `project.progress` | 0–100% | All |
| F-101 | Overdue indicator | `project.is_overdue` | End date passed | All |
| F-102 | Project incharge display | template | Single lead user | All |
| F-103 | Visibility badge | private/public | `Project.visibility` | All |
| F-104 | Custom background/button colors | settings | Branding | Editors |
| F-105 | Cover image upload | `project.image` | Banner | Editors |
| F-106 | Edit project metadata | `/projects/<pk>/edit/` | | A/PM/IC |
| F-107 | Project settings page | `/projects/<pk>/settings/` | Advanced | A/PM/IC |
| F-108 | Manage members & managers | `/projects/<pk>/members/` | M2M | A/PM/IC |
| F-109 | Dual-flag delete request | delete view | admin + PM flags | A/PM |
| F-110 | Cancel deletion request | `ProjectService` | Per-role cancel | A/PM |
| F-111 | Archive toggle | `/projects/<pk>/archive/` | `is_archived` | A/PM/IC |
| F-112 | Request institute release | `request-release` | `release_requested` | A/PM/IC |
| F-113 | Approve institute release | `approve-release` | `is_released` | A/PM |
| F-114 | Dedicated project task page | `/projects/<pk>/tasks/` | Filters | Members+ |
| F-115 | Dedicated requirements page | `.../requirements/` | | Members+ |
| F-116 | Dedicated project bugs page | `.../bugs/` | | Members+ |
| F-117 | Resource view: tree | `?resource_view=tree` | Folder hierarchy | Members+ |
| F-118 | Resource view: grid | `resource_view=grid` | Card layout | Members+ |
| F-119 | Resource view: table | `resource_view=repository` | Dense table | Members+ |
| F-120 | Drill into category `repo_cat_id` | GET param | Subfolder focus | Members+ |
| F-121 | Resource folder comments | POST on detail | Category discussion | IC/PM |
| F-122 | SRS/BRD/FRD report modal | `#report-modal` | Template + format pick | IC/PM/A |
| F-123 | Task report modal | project detail | Export tasks | IC/PM/A |
| F-124 | Student: phase releases only | `release_list` filter | Hides draft partials | S |
| F-125 | Task count / completed count | `@property` on Project | Sidebar stats | All |
| F-126 | `latest_files` property | Project model | Latest version files only | All |

---

# PART D — TASKS (21+ features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-127 | Global task list | `/tasks/` | Filters + pagination | Scoped |
| F-128 | Filter status/priority | GET params | | All |
| F-129 | My tasks `?mine=1` | task_list | assignees=me | All |
| F-130 | Filter by project | `?project=` | | All |
| F-131 | Overdue filter `?overdue=1` | task_list | | All |
| F-132 | Sort `?sort=` | default `-updated_at` | | All |
| F-133 | Bulk create tasks | `/projects/<pk>/tasks/bulk/` | Formset | A/PM/IC |
| F-134 | Create single task | `/tasks/new/` | | Members+ |
| F-135 | Pre-fill project/module `?project=&module=` | task_create | | All |
| F-136 | Task detail page | `/tasks/<pk>/` | Full hub | Viewers |
| F-137 | Threaded comments | task_detail | parent replies | Viewers |
| F-138 | Comment attachments | Comment model | File upload | Viewers |
| F-139 | Auto-mark notifications read | task_detail view | On open | Assignees |
| F-140 | Subtasks list | parent_task FK | Hierarchy | Viewers |
| F-141 | Linked bugs panel | task_detail | BugReport FK | Viewers |
| F-142 | Linked KB notes sidebar | task_detail | | Viewers |
| F-143 | File version tree partial | `file_version_node.html` | Version chain UI | Viewers |
| F-144 | Edit task | `/tasks/<pk>/edit/` | sprint, story points, hours | Editors |
| F-145 | Soft delete task | `/tasks/<pk>/delete/` | Trash | Editors |
| F-146 | Approve task (`is_approved`) | `/tasks/<pk>/approve/` | Member visibility gate | A/PM |
| F-147 | AJAX Kanban status POST | `/tasks/<pk>/status/` | JSON response + progress | IC/PM/A |
| F-148 | Block done if tests fail | status API 400 | `can_complete` | System |
| F-149 | Release-ready notify | status view | All release tasks reviewed | System |
| F-150 | Notify assignees on status change | NotificationService | | System |
| F-151 | Auto task ID | `Task.save` | TAS/BUG/FEA-… | System |
| F-152 | `tag_list` from comma tags | Task.tags | Split property | All |
| F-153 | `is_overdue` on task | property | | All |
| F-154 | `test_case_stats` property | passed/failed/% | | All |
| F-155 | Sprint link | Task.sprint | Agile | Editors |
| F-156 | Milestone text field | Task.milestone | | Editors |
| F-157 | Story points | Task.story_points | | Editors |
| F-158 | Estimated/actual hours | decimal fields | | Editors |
| F-159 | Task types: task/bug/feature/improvement/research | choices | | All |
| F-160 | Task link to requirement | FK | Traceability | Editors |
| F-161 | Task link to release | FK | Cut line | Editors |
| F-162 | AJAX get project data | `/ajax/get-project-data/` | Modules/members JSON | All |
| F-163 | API tasks for project | `/api/tasks-for-project/` | | All |
| F-164 | Auto-add assignees to module | signals m2m | ModuleMember | System |
| F-165 | Auto-add assignees to project.members | signals | | System |

---

# PART E — REQUIREMENTS (11+ features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-166 | Requirement types (8 kinds) | BRD/FRD/TRD/UI/security/API/DB/NFR | Typed specs | All |
| F-167 | Status workflow 7 states | draft→deprecated | Badge colors | All |
| F-168 | M2M dependencies | Requirement.dependencies | Graph | Editors |
| F-169 | Version counter | Requirement.version | Increments | System |
| F-170 | `RequirementVersion` history | versions relation | Audit trail | A/PM |
| F-171 | Approve requirement | `/requirements/<pk>/approve/` | `is_approved` | IC/PM/A |
| F-172 | Requirement progress % | property from child tasks | | All |
| F-173 | Bulk create requirements | formset | | IC/PM/A |
| F-174 | Export requirement report | `?format=&template=srs` | PDF/DOCX/XLSX/MD | Members+ |
| F-175 | Assigned team text field | `assigned_team` | | Editors |
| F-176 | Auto REQ ID | `REQ-{prefix}-{year}-####` | | System |
| F-177 | Requirement trash/restore | misc_views | | A/PM |

---

# PART F — MODULES & FORUM (8 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-178 | Module list per project | `/projects/<pk>/modules/` | | Members+ |
| F-179 | Create module | module_create | | IC/PM/A |
| F-180 | Module detail | `/modules/<pk>/` | Tasks, reqs, files | MM+ |
| F-181 | Module forum posts | module_detail | Attachments | MM+ |
| F-182 | Forum reply `showReplyForm` | JS onclick | Inline reply | MM+ |
| F-183 | Module member roles | designer/developer/tester | ModuleMember | IC/PM/A |
| F-184 | Edit/delete module | module views | | IC/PM/A |
| F-185 | Module-scoped file access | `check_file_access` | ModuleMember check | System |

---

# PART G — RELEASES & CI/CD (23+ features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-186 | Project release list | `/projects/<pk>/releases/` | | Members+ |
| F-187 | Global release search | `/releases/?q=` | Cross-project | A/PM |
| F-188 | Create release | release_create | Snapshot options | A/PM |
| F-189 | Release without project | `/releases/new/` | pk=0 route | A/PM |
| F-190 | Release detail file tree | release_detail | SHA display | All |
| F-191 | Draft flag | `is_draft` | Hidden from students | Editors |
| F-192 | Prerelease flag | `is_prerelease` | | Editors |
| F-193 | Publish release | `/releases/<pk>/publish/` | Locks release | A/PM |
| F-194 | Release lock enforcement | `Release.save` ValidationError | No edits when completed | System |
| F-195 | SHA-256 per ReleaseFile | `content_hash` | Integrity | All |
| F-196 | Download release ZIP | release_download | Full bundle | Members+ |
| F-197 | Download selected assets ZIP | POST assets/download | Partial bundle | Members+ |
| F-198 | Single asset download | asset download URL | | Members+ |
| F-199 | Upload extra release asset | asset_upload | `is_extra_asset=True` | A/PM |
| F-200 | Compare two releases | `?with=` release_compare | Diff UI | Members+ |
| F-201 | Restore release to project | release_restore | Rollback files | A/PM |
| F-202 | Release deletion request | deletion_request form | Queue | Members |
| F-203 | Admin deletion queue | admin_deletion_requests | Approve/reject | A |
| F-204 | CI/CD page | `/projects/<pk>/cicd/` | PipelineRun list | Members+ |
| F-205 | Pipeline run status badges | pending/running/passed/failed | | All |
| F-206 | Trigger commit hash field | PipelineRun | Git integration display | All |
| F-207 | ReleaseLog audit trail | per-release actions | snapshot/publish | A/PM |
| F-208 | Sync published assets to project Releases/ folder | ReleaseService | ZIP + copies | System |
| F-209 | Include subfolders on snapshot | release form option | Recursive | A/PM |
| F-210 | Release compare file tree node | partial template | Nested UI | All |

---

# PART H — BUGS (9 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-211 | Bug list filters | severity/status/project/assigned | | Scoped |
| F-212 | Assigned to me filter | `?assigned_to_me=` | | All |
| F-213 | Auto-create linked task on assign | bug_create | `[Bug] title` task | System |
| F-214 | Steps to reproduce fields | BugReport | QA template | Reporters |
| F-215 | Expected vs actual behavior | text fields | | Reporters |
| F-216 | Resolution attachment upload | resolve form | PDF/logs | Resolvers |
| F-217 | Resolution summary & solving results | text | | Resolvers |
| F-218 | wont_fix status | terminal | PM/IC only | IC/PM/A |
| F-219 | Soft delete + trash restore | misc_views | | A/PM |

---

# PART I — TEST CASES (9 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-220 | TC statuses: pending/passed/failed/blocked/retest | badges | | All |
| F-221 | Approval status on TC | pending/approved/rejected | | Verifiers |
| F-222 | Verify page with attachments | test_case_verify | Evidence upload | Verifiers |
| F-223 | TestCaseHistory log | auto on verify | | All |
| F-224 | TC blocks task done | enforced API | | System |
| F-225 | Notify PM when all TCs pass | verify view | ready for completion | System |
| F-226 | Bulk TC create | formset | | IC/PM/A |
| F-227 | Export test report | test-report URL | PDF etc. | Members+ |
| F-228 | Pre-fill task on create `?task=` | test_case_create | | All |

---

# PART J — KNOWLEDGE BASE (9 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-229 | Global KB overview | `/knowledge-base/` | Cross-project | All |
| F-230 | Filter KB `?q=&project=&author=` | kb_overview | | All |
| F-231 | Global note create | kb_create_global | No project | All |
| F-232 | Project KB list | project kb_list | | Members+ |
| F-233 | Markdown content | KnowledgeBaseNote | Rendered in detail | All |
| F-234 | Auto-sync to ProjectFile .md | note.save | Notes category | System |
| F-235 | Per-note access rights page | kb_access | DocumentAccessRight | Managers |
| F-236 | Module-scoped notes | module FK | | Editors |
| F-237 | KB trash restore | misc_views | | A/PM |

---

# PART K — FILES & ANNOTATIONS (30+ features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-238 | File type detection (12 types) | ProjectFile.detect_file_type | image/pdf/code/CAD… | System |
| F-239 | Icon class/color per type | properties | Font Awesome | UI |
| F-240 | `file_size_display` human readable | KB/MB/GB | | UI |
| F-241 | `is_previewable` / `is_text_viewable` | browser inline | | UI |
| F-242 | Multi-file upload | file_upload | AJAX JSON response | Uploaders |
| F-243 | Drag-drop upload zone | file_upload.html | | Uploaders |
| F-244 | Version chain parent_file | versioning | v1→v2→v3 | All |
| F-245 | Physical path rename on category rename | FileCategory.save cascade | Files move on disk | System |
| F-246 | Download count increment | download view | Analytics | System |
| F-247 | Public file flag | is_public | All members download | Editors |
| F-248 | Per-user file ACL page | file_access | view/edit/delete | PM/A |
| F-249 | Inline content editor | file_content_edit | .md/.py/.txt | Editors |
| F-250 | Copy code button | file_detail template | Clipboard | Viewers |
| F-251 | PDF.js inline viewer | file_view | | Viewers |
| F-252 | Document discussion page | document_discussion | Full-screen review | Viewers |
| F-253 | PDF highlight annotations | annotation_coords JSON | Color picker | Reviewers |
| F-254 | PDF page number on comment | page_number field | | Reviewers |
| F-255 | Assign comment to user | assigned_to FK | | Reviewers |
| F-256 | PDF zoom in/out buttons | client JS | | Viewers |
| F-257 | Download PDF with annotations | `?download=with_annotations` | embed_pdf_annotations | Viewers |
| F-258 | Download clean PDF | without annotations | | Viewers |
| F-259 | Folder discussion (no PDF) | folder_discussion | Category thread | Members+ |
| F-260 | AJAX comment post/reply | discussion views | | Participants |
| F-261 | Folder ZIP download | download_folder | Latest files only | Viewers |
| F-262 | Move file/folder | move_item | Pick target category | PM+ |
| F-263 | hide-from-trash personal | hide_from_trash | User-specific | Owner |
| F-264 | Dual-approval permanent delete | admin_approved + pm_approved | | A/PM |
| F-265 | File audit log page | file_audit_logs | | PM/A |
| F-266 | Max upload GB setting | files SystemSettings | Admin | A |
| F-267 | Category tree expand/collapse | category_tree.html | | Viewers |

---

# PART L — CALENDAR (8 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-268 | FullCalendar month/week/day | calendar.html | | All |
| F-269 | Event types 5 kinds | milestone/meeting/… | Color coded | All |
| F-270 | Meeting link + password fields | CalendarEvent | Video conf | Creators |
| F-271 | Location field | physical room | | Creators |
| F-272 | M2M attendees | notifications on create | | Creators |
| F-273 | Task due/deadline overlay | calendar_view | Read-only events | Owner |
| F-274 | Google sync push | calendar_sync.py | | If OAuth |
| F-275 | CalDAV two-way sync | calendar_sync | Radicale | If enabled |

---

# PART M — CHAT (16+ features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-276 | Room list unread badges | chat_home | Per-room count | All |
| F-277 | DM normalized room IDs | DM-min-max | Stable WS group | System |
| F-278 | Typing indicator | WS typing event | Ephemeral | All |
| F-279 | Message edit (10 min window) | WS edit_message | | Sender |
| F-280 | Soft delete message | is_deleted flag | | Sender |
| F-281 | Message reactions emoji | MessageReaction | Toggle | All |
| F-282 | Voice note message type | message_type=voice | | All |
| F-283 | Task link message type | message_type=task_link | | All |
| F-284 | System messages | message_type=system | Join/leave | System |
| F-285 | Chat file attachments | ChatAttachment | Auto-delete file on row delete | All |
| F-286 | Forward single/bulk messages | forward API + modal | | All |
| F-287 | Bulk select delete mode | bulk_delete API | | All |
| F-288 | Per-user clear chat | ChatClear | Hide history | All |
| F-289 | NotificationConsumer WS | ws/notifications/ | Navbar live update | All |
| F-290 | Gemini summarize chat | ai_utils (backend) | Needs API key | Optional |
| F-291 | Gemini extract tasks from chat | ai_utils | Suggested actions | Optional |
| F-292 | Room avatar image | room_picture | Group chats | Creators |
| F-293 | DM avatar from other user photo | get_avatar_url | | All |

---

# PART N — NOTIFICATIONS (8 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-294 | 14 notification types | Notification model | See encyclopedia | System |
| F-295 | Default filter unread | notifications list | | All |
| F-296 | Filter by timeframe | GET param | today/week/month | All |
| F-297 | Deep link on read | task/project/chat | | All |
| F-298 | Skip self-notify | NotificationService | No echo | System |
| F-299 | Live unread via Channels | WebSocket | | All |

---

# PART O — REPORTS & RTM (11 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-300 | Chart.js task status pie | reports.html | | PM/M |
| F-301 | Module workload bar chart | reports_view | Open tasks | PM/M |
| F-302 | Overdue tasks table | reports | | PM/M |
| F-303 | Report center format picker | report_center | pdf/docx/xlsx/md | PM/M |
| F-304 | Master report all sections | ReportEngine.generate_master_report | 8+ sections | Members+ |
| F-305 | RTM matrix HTML | rtm_view | Req→Task→TC | Members+ |
| F-306 | Unicode dash fix in PDF | format_text_pdf | Typography | System |
| F-307 | Styled DOCX tables | report_engine | Corporate style | System |
| F-308 | Multi-sheet XLSX master | openpyxl | | Members+ |
| F-309 | Project report center + audit excerpt | project_report_center | | Members+ |
| F-310 | Template type SRS/BRD/FRD | requirement report | | Members+ |

---

# PART P — FINANCE, TRASH, AUDIT

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-311 | Expense categories (6) | Expense model | hardware/software/… | PM/A |
| F-312 | Receipt link to ProjectFile | Expense.receipt FK | | PM/A |
| F-313 | Remaining budget display | template | live calc | All |
| F-314 | Unified trash 7 entity types | `/trash/` | One page | A/PM/own |
| F-315 | Trash filter by deleter | `?deleted_by=` | Admin only list | A/PM |
| F-316 | Trash filter by age days | `?days=` | | A/PM |
| F-317 | PM audit log filters | module/action/user | `/audit-logs/` | A |
| F-318 | Login IP in audit | signals | user_agent stored | A |

---

# PART Q — INVENTORY (50 features) — Summary Table

*Full 50 rows documented in agent exploration; key mini-features below.*

| ID | Feature | Description | Access |
|----|---------|-------------|--------|
| F-319 | Branch multi-site | Unique branch codes | Inv |
| F-320 | BranchStock ledger | Auto-recalc from entries | System |
| F-321 | Reserved quantity field | Future hold stock | Inv |
| F-322 | Rack/shelf/local SKU | Per-branch location | Inv |
| F-323 | Stock in bulk Excel | 5MB limit template | Staff |
| F-324 | Stock out quantity cap | Cannot exceed available | System |
| F-325 | Transfer pending→received | Two-step workflow | Staff |
| F-326 | Transfer rack at receive | Updates destination | Receiver |
| F-327 | Manual adjustment increase/decrease | Signed qty | Permitted |
| F-328 | Serial tracked assets | unique serial_number | Permitted |
| F-329 | Serial statuses 4 kinds | available/sold/returned/damaged | All |
| F-330 | Quantity limits per branch | Alert threshold | Managers |
| F-331 | Standard limit global default | set_standard_limit | Admin |
| F-332 | Alert acknowledge/resolve | Two-step lifecycle | Managers |
| F-333 | Rental check-out/in | Stock entries auto | Rentals perm |
| F-334 | Overdue rental highlight | UI styling | Viewers |
| F-335 | Shortage report | Below limit products | Viewers |
| F-336 | Shortage CSV export | | Export perm |
| F-337 | Shortage PDF export | | Export perm |
| F-338 | Procurement Excel upload | Pending requests | Staff |
| F-339 | Procurement approve→stock in | Notifies requester | Admin |
| F-340 | Procurement reject reason | decision_reason required | Admin |
| F-341 | send-all-alerts bulk | procurement API | Admin |
| F-342 | Product bulk Excel import | Skip duplicates | Add perm |
| F-343 | Product image + datasheet | FileFields | Editors |
| F-344 | Category default seed (9) | management command | Setup |
| F-345 | Inventory notifications page | Separate from PM | Inv |
| F-346 | Super admin branch CRUD | Cannot delete if stock | Super |
| F-347 | Branch staff management | branch_admin | Branch admin |
| F-348 | DB backup button | settings db-backup | Super admin |
| F-349 | Statistics 12-month charts | reports app | Export perm |
| F-350 | Inventory REST APIs | products/stock/adjustments | API auth |
| F-351 | `can_view_all_branches` flag | Cross-branch visibility | Super |
| F-352 | Middleware page ACL | 6 protected prefixes | System |
| F-353 | check_alerts cron command | Auto alert rows | Ops |
| F-354 | recalculate_stock command | Integrity repair | Ops |

---

# PART R — TELESCOPE (7 features)

| ID | Feature | Location | Description | Access |
|----|---------|----------|-------------|--------|
| F-355 | Observatory dashboard grid | `/telescope/` | All instruments | Tel |
| F-356 | Weather panel (static/demo) | dashboard template | Context display | Tel |
| F-357 | Auto-seed 5 telescopes | ensure_default_telescopes | First visit | System |
| F-358 | Live status fields | observing/idle/maintenance | | Tel |
| F-359 | RA/Dec/target/dome/CCD/tracking | detail fields | Engineering | Tel |
| F-360 | External image URL fallback | image_url field | | Admin |
| F-361 | Tel admin CRUD | create/edit/delete | | Tel admin |

---

# PART S — SYSTEM & MODEL MINI-FEATURES (Often Missed)

| ID | Feature | Location | Description |
|----|---------|----------|-------------|
| F-362 | `SystemIssue` institute tickets | tasks.models | Platform feedback |
| F-363 | `ReleaseDeletionRequest` workflow | tasks.models | Release delete approval |
| F-364 | `ReleaseModuleVersion` | tasks.models | Per-module version in release |
| F-365 | `Sprint` active/completed flags | tasks.models | Sprint planning |
| F-366 | `PipelineRun` duration_seconds | tasks.models | CI timing |
| F-367 | `UserCalendarSettings` JSON OAuth token | events.models | Google token storage |
| F-368 | `UserPresence` online flag | chat.models | Presence |
| F-369 | `ReadReceipt` per message user | chat.models | WhatsApp-style |
| F-370 | `InventoryNotification` separate table | inventory.models | Not PM Notification |
| F-371 | `StandardLimit` singleton-style | inventory.models | Default threshold |
| F-372 | `seed_data` management command | tasks/management | Demo users/projects |
| F-373 | Template tags: getitem, subtract, multiply, split | task_tags.py | Template math |
| F-374 | `basename` filter for paths | task_tags.py | Display filenames |
| F-375 | Context: sidebar_projects prefetch | processor | kb, bugs, files |
| F-376 | Student role visibility rules | multiple views | Reduced releases |
| F-377 | Public project visibility | Project.visibility | Wider read |
| F-378 | Email notify on calendar event | event_create | Members emailed |
| F-379 | Paginator on all long lists | 10-25 per page | Performance |
| F-380 | `messages` framework flash | Django | User feedback |
| F-381 | File post_delete signal | chat ChatAttachment | Disk cleanup |
| F-382 | Requirement assigned_team text | Requirement | Team label |
| F-383 | Task order field for Kanban | Task.order | Sort within column |
| F-384 | Project deletion_requested_at timestamp | Project | Audit when requested |
| F-385 | Hidden file from user trash | ProjectFile flag | Per-user trash view |
| F-386 | Release metadata JSONField | Release.metadata | Extensibility |
| F-387 | Expense date_incurred | finance | Backdated expenses |
| F-388 | Bug linked_task FK | bugs | Sync with tasks |
| F-389 | TestCase verified_by/date | testcases | QA sign-off |
| F-390 | DocumentAccessRight on KB | files.models | Note permissions |

---

# PART T — REQUIREMENTS TRACEABILITY (Features ↔ Specs)

## T.1 Original README Module Goals

| README promise | Implemented features (IDs) |
|----------------|---------------------------|
| Authentication | F-001–F-054 |
| Dashboard | F-069–F-078 |
| Projects CRUD | F-079–F-126 |
| Tasks list & Kanban | F-127–F-165, F-097–F-098 |
| Calendar | F-268–F-275 |
| Bug reports | F-211–F-219 |
| Notifications | F-294–F-299 |
| Reports | F-300–F-310 |
| User management | F-029–F-051 |
| File management (roadmap) | F-238–F-267 |
| Inventory (roadmap) | F-319–F-354 |
| Finance (roadmap) | F-311–F-313 |

## T.2 Non-Functional Requirements Covered

| NFR | Feature evidence |
|-----|------------------|
| Role-based access | Decorators, middleware, query_utils |
| Auditability | F-317–F-318, F-265, inventory audit |
| Data integrity | F-195, F-320, release lock F-194 |
| Real-time UX | F-276–F-291 |
| Large files | F-266, 10GB settings |
| Multi-branch inventory | F-319–F-354 |

---

# PART U — FEATURE COUNT BY MODULE

| Module | Features |
|--------|----------|
| Accounts & shell | 68 |
| Dashboard & search | 10 |
| Projects | 48 |
| Tasks | 39 |
| Requirements | 12 |
| Modules | 8 |
| Releases | 25 |
| Bugs | 9 |
| Test cases | 9 |
| Knowledge base | 9 |
| Files | 30 |
| Calendar | 8 |
| Chat | 18 |
| Notifications | 6 |
| Reports | 11 |
| Finance/trash/audit | 8 |
| Inventory | 36 |
| Telescope | 7 |
| System mini | 29 |
| **Total** | **390** |

---

*For narrative chapters and deployment guides, see `PROJECT_REPORT_MASTER_PART1-3.md`. For function-level pseudocode, see `PROJECT_REPORT_CODE_ENCYCLOPEDIA.md`.*
