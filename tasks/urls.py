from django.urls import path
from .views import (
    dashboard_views,
    project_views,
    task_views,
    report_views,
    module_views,
    release_views,
    misc_views,
    audit_views,
)
from bugs import views as bug_views
from notifications import views as notification_views
from events import views as calendar_views
from testcases import views as test_case_views
from notes import views as kb_views
from files.views import detail_views as files_detail_views
from .api import endpoints

app_name = "tasks"

urlpatterns = [
    # Document Discussion
    path(
        "projects/<int:project_id>/document/<int:doc_id>/discussion/",
        files_detail_views.document_discussion,
        name="document_discussion",
    ),
    # Folder Discussion
    path(
        "projects/<int:project_id>/folder/<int:folder_id>/discussion/",
        files_detail_views.folder_discussion,
        name="folder_discussion",
    ),
    # Dashboard
    path("dashboard/", dashboard_views.dashboard, name="dashboard"),
    # Search
    path("search/", misc_views.global_search, name="global_search"),
    # Projects
    path("projects/", project_views.project_list, name="project_list"),
    path("projects/new/", project_views.project_create, name="project_create"),
    path("projects/<int:pk>/", project_views.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", project_views.project_edit, name="project_edit"),
    path(
        "projects/<int:pk>/settings/",
        project_views.project_settings,
        name="project_settings",
    ),
    path(
        "projects/<int:pk>/tasks/",
        project_views.project_task_list,
        name="project_task_list",
    ),
    path(
        "projects/<int:pk>/requirements/",
        project_views.project_requirement_list,
        name="project_requirement_list",
    ),
    path(
        "projects/<int:pk>/bugs/",
        project_views.project_bug_list,
        name="project_bug_list",
    ),
    path(
        "projects/<int:pk>/members/",
        project_views.project_members,
        name="project_members",
    ),
    path(
        "projects/<int:pk>/delete/", project_views.project_delete, name="project_delete"
    ),
    path(
        "projects/<int:pk>/archive/", project_views.project_archive_toggle, name="project_archive"
    ),

    path(
        "projects/<int:pk>/cicd/", release_views.project_cicd, name="project_cicd"
    ),  # Moved to release_views conceptually or keep in project
    # Requirements
    path(
        "projects/<int:pk>/requirements/bulk/",
        release_views.requirement_bulk_create,
        name="requirement_bulk_create",
    ),
    path(
        "projects/<int:pk>/requirements/new/",
        release_views.requirement_create,
        name="requirement_create",
    ),
    path(
        "requirements/<int:pk>/",
        release_views.requirement_detail,
        name="requirement_detail",
    ),
    path(
        "requirements/<int:pk>/edit/",
        release_views.requirement_edit,
        name="requirement_edit",
    ),
    path(
        "requirements/<int:pk>/delete/",
        release_views.requirement_delete,
        name="requirement_delete",
    ),
    path(
        "requirements/<int:pk>/approve/",
        release_views.requirement_approve,
        name="requirement_approve",
    ),
    path(
        "requirements/<int:pk>/restore/",
        misc_views.requirement_restore,
        name="requirement_restore",
    ),
    path(
        "requirements/<int:pk>/permanent-delete/",
        misc_views.requirement_permanent_delete,
        name="requirement_permanent_delete",
    ),
    path(
        "projects/<int:pk>/requirements/report/",
        release_views.requirement_report,
        name="requirement_report",
    ),
    # Modules
    path("projects/<int:pk>/modules/", module_views.module_list, name="module_list"),
    path(
        "projects/<int:pk>/modules/new/",
        module_views.module_create,
        name="module_create",
    ),
    path("modules/<int:pk>/", module_views.module_detail, name="module_detail"),
    path("modules/<int:pk>/edit/", module_views.module_edit, name="module_edit"),
    path("modules/<int:pk>/delete/", module_views.module_delete, name="module_delete"),
    path(
        "modules/<int:pk>/members/", module_views.module_members, name="module_members"
    ),
    # Releases
    path(
        "projects/<int:pk>/releases/", release_views.release_list, name="release_list"
    ),
    path(
        "projects/<int:pk>/releases/new/",
        release_views.release_create,
        name="release_create",
    ),
    path(
        "releases/new/",
        release_views.release_create,
        {"pk": 0},
        name="release_create_no_project",
    ),
    path("releases/<int:pk>/", release_views.release_detail, name="release_detail"),
    path("releases/<int:pk>/edit/", release_views.release_edit, name="release_edit"),
    path(
        "releases/<int:pk>/delete/", release_views.release_delete, name="release_delete"
    ),
    path(
        "releases/<int:pk>/download/",
        release_views.release_download,
        name="release_download",
    ),
    path(
        "releases/<int:pk>/assets/download/",
        release_views.release_assets_download,
        name="release_assets_download",
    ),
    path(
        "releases/assets/<int:pk>/download/",
        release_views.release_asset_download,
        name="release_asset_download",
    ),
    path(
        "releases/<int:pk>/compare/",
        release_views.release_compare,
        name="release_compare",
    ),
    path(
        "releases/<int:pk>/restore/",
        release_views.release_restore,
        name="release_restore",
    ),
    path(
        "releases/<int:pk>/publish/",
        release_views.release_publish,
        name="release_publish",
    ),
    path(
        "releases/<int:pk>/assets/upload/",
        release_views.release_asset_upload,
        name="release_asset_upload",
    ),
    path(
        "releases/<int:pk>/delete-request/",
        release_views.release_deletion_request,
        name="release_deletion_request",
    ),
    path(
        "releases/admin/deletion-requests/",
        release_views.admin_deletion_requests,
        name="admin_deletion_requests",
    ),
    path(
        "releases/admin/deletion-resolve/<str:req_type>/<int:pk>/",
        release_views.resolve_deletion_request,
        name="resolve_deletion_request",
    ),
    path("releases/", release_views.global_release_list, name="global_release_list"),
    # Knowledge Base
    path("knowledge-base/", kb_views.kb_overview, name="kb_overview"),
    path("knowledge-base/new/", kb_views.kb_create_global, name="kb_create_global"),
    path("projects/<int:pk>/knowledge-base/", kb_views.kb_list, name="kb_list"),
    path("projects/<int:pk>/knowledge-base/new/", kb_views.kb_create, name="kb_create"),
    path("knowledge-base/<int:pk>/", kb_views.kb_detail, name="kb_detail"),
    path("knowledge-base/<int:pk>/edit/", kb_views.kb_edit, name="kb_edit"),
    path("knowledge-base/<int:pk>/access/", kb_views.kb_access, name="kb_access"),
    path("knowledge-base/<int:pk>/delete/", kb_views.kb_delete, name="kb_delete"),
    path("knowledge-base/<int:pk>/restore/", kb_views.note_restore, name="note_restore"),
    path("knowledge-base/<int:pk>/permanent-delete/", kb_views.note_permanent_delete, name="note_permanent_delete"),
    # Tasks
    path("tasks/", task_views.task_list, name="task_list"),
    path(
        "projects/<int:pk>/tasks/bulk/",
        task_views.task_bulk_create,
        name="task_bulk_create",
    ),
    path("ajax/get-project-data/", task_views.get_project_data, name="get_project_data"),
    path("projects/<int:project_id>/test-cases/bulk/", test_case_views.test_case_bulk_create, name="project_test_case_bulk_create"),
    path("tasks/new/", task_views.task_create, name="task_create"),
    path("tasks/<int:pk>/", task_views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", task_views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", task_views.task_delete, name="task_delete"),
    path("tasks/<int:pk>/approve/", task_views.task_approve, name="task_approve"),
    path("tasks/<int:pk>/restore/", misc_views.task_restore, name="task_restore"),
    path("tasks/<int:pk>/permanent-delete/", misc_views.task_permanent_delete, name="task_permanent_delete"),
    path(
        "tasks/<int:pk>/status/",
        task_views.task_update_status,
        name="task_update_status",
    ),
    path(
        "projects/<int:pk>/tasks/report/", release_views.task_report, name="task_report"
    ),
    # Notifications (served under tasks: namespace — templates use tasks:notifications)
    path("notifications/", notification_views.notifications_list, name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        notification_views.notification_read,
        name="notification_read",
    ),
    # Bugs (served under tasks: namespace — templates use tasks:bug_list etc.)
    path("bugs/", bug_views.bug_list, name="bug_list"),
    path("bugs/new/", bug_views.bug_create, name="bug_create"),
    path("bugs/<int:pk>/", bug_views.bug_detail, name="bug_detail"),
    path("bugs/<int:pk>/edit/", bug_views.bug_edit, name="bug_edit"),
    path("bugs/<int:pk>/comment/", bug_views.bug_comment_add, name="bug_comment_add"),
    path("bugs/<int:pk>/resolve/", bug_views.bug_resolve, name="bug_resolve"),
    path("bugs/<int:pk>/delete/", bug_views.bug_delete, name="bug_delete"),
    path("bugs/<int:pk>/restore/", misc_views.bug_restore, name="bug_restore"),
    path("bugs/<int:pk>/permanent-delete/", misc_views.bug_permanent_delete, name="bug_permanent_delete"),
    # Test Cases (served under tasks: namespace — templates use tasks:test_case_detail etc.)
    path("projects/<int:project_id>/test-cases/new/", test_case_views.test_case_create, name="test_case_create"),
    path("projects/<int:project_id>/test-cases/bulk/", test_case_views.test_case_bulk_create, name="project_test_case_bulk_create"),
    path("test-cases/<int:pk>/", test_case_views.test_case_detail, name="test_case_detail"),
    path("test-cases/<int:pk>/edit/", test_case_views.test_case_edit, name="test_case_edit"),
    path("test-cases/<int:pk>/delete/", test_case_views.test_case_delete, name="test_case_delete"),
    path("test-cases/<int:pk>/restore/", misc_views.testcase_restore, name="test_case_restore"),
    path("test-cases/<int:pk>/permanent-delete/", misc_views.testcase_permanent_delete, name="test_case_permanent_delete"),
    path("test-cases/<int:pk>/verify/", test_case_views.test_case_verify, name="test_case_verify"),
    # Calendar (served under tasks: namespace — templates use tasks:calendar etc.)
    path("calendar/", calendar_views.calendar_view, name="calendar"),
    path("calendar/google/init/", calendar_views.google_calendar_init, name="google_calendar_init"),
    path("calendar/google/callback/", calendar_views.google_calendar_callback, name="google_calendar_callback"),
    path("calendar/toggle-caldav-sync/", calendar_views.toggle_caldav_sync, name="toggle_caldav_sync"),
    path("calendar/event/new/", calendar_views.event_create, name="event_create"),
    path("calendar/event/<int:pk>/", calendar_views.event_detail, name="event_detail"),
    path("calendar/event/<int:pk>/edit/", calendar_views.event_edit, name="event_edit"),
    path("calendar/event/<int:pk>/delete/", calendar_views.event_delete, name="event_delete"),
    # API Endpoints
    path(
        "api/tasks-for-project/", endpoints.tasks_for_project, name="tasks_for_project"
    ),
    path(
        "api/project-modules/",
        endpoints.project_modules_api,
        name="project_modules_api",
    ),
    path(
        "api/project-requirements/",
        endpoints.project_requirements_api,
        name="project_requirements_api",
    ),
    path(
        "api/project-members/",
        endpoints.project_members_api,
        name="project_members_api",
    ),
    # Misc
    path("reports/", report_views.reports_view, name="reports"),
    path("pm-inventory/", misc_views.inventory_list, name="inventory_list"),
    # Report Center
    path("report-center/", report_views.report_center, name="report_center"),
    path("projects/<int:pk>/report-center/", report_views.project_report_center, name="project_report_center"),
    path("projects/<int:pk>/master-report/", report_views.master_report, name="master_report"),
    path("rtm/<int:pk>/", release_views.rtm_view, name="rtm_view"),
    path("test-report/<int:pk>/", release_views.test_case_report, name="test_case_report"),
    # Audit Viewer
    path("audit-logs/", audit_views.audit_log_list, name="audit_log_list"),
    # Trash
    path("trash/", misc_views.trash_view, name="trash"),
    path("trash/bulk-restore/", misc_views.trash_bulk_restore, name="trash_bulk_restore"),
    path("folders/<int:pk>/restore/", misc_views.category_restore, name="category_restore"),
    path("folders/<int:pk>/permanent-delete/", misc_views.category_permanent_delete, name="category_permanent_delete"),
]
