from django.urls import path
from . import views

app_name = "telescope"

urlpatterns = [
    # Mission Control / Dashboard
    path("", views.dashboard, name="dashboard"),
    
    # Telescope System Control
    path("telescopes/", views.telescope_list, name="telescope_list"),
    path("telescopes/create/", views.telescope_create, name="telescope_create"),
    path("telescopes/vbt/", views.telescope_detail, {'code': 'vbt'}, name="telescope_vbt"),
    path("telescopes/jcbt/", views.telescope_detail, {'code': 'jcbt'}, name="telescope_jcbt"),
    path("telescopes/czt/", views.telescope_detail, {'code': 'czt'}, name="telescope_czt"),
    path("telescopes/<int:pk>/", views.telescope_detail, name="telescope_detail"),
    path("telescopes/<int:pk>/edit/", views.telescope_edit, name="telescope_edit"),
    path("telescopes/<int:pk>/delete/", views.telescope_delete, name="telescope_delete"),
    path("telescopes/<int:pk>/slew/", views.slew_telescope, name="telescope_slew"),
    path("telescopes/<int:pk>/stop/", views.stop_telescope, name="stop_telescope"),
    path("telescopes/<int:pk>/park/", views.park_telescope, name="park_telescope"),
    path("telescopes/<int:pk>/toggle-dome/", views.toggle_dome, name="toggle_dome"),
    path("telescopes/<int:pk>/update-telemetry/", views.update_telemetry, name="update_telemetry"),

    # Discussions Hub
    path("discussions/", views.discussion_hub, name="discussion_hub"),
    path("discussions/create/", views.discussion_create, name="discussion_create"),
    path("discussions/<int:pk>/", views.discussion_detail, name="discussion_detail"),
    path("discussions/<int:pk>/pin/", views.toggle_pin_discussion, name="toggle_pin_discussion"),

    # Instruments Hub
    path("instruments/", views.instrument_list, name="instrument_list"),
    path("instruments/create/", views.instrument_create, name="instrument_create"),
    path("instruments/<int:pk>/", views.instrument_detail, name="instrument_detail"),
    path("instruments/<int:pk>/edit/", views.instrument_edit, name="instrument_edit"),
    path("instruments/<int:pk>/status/", views.update_status, name="update_status"),

    # Science Operations & Targets
    path("targets/", views.target_list, name="target_list"),
    path("targets/create/", views.target_create, name="target_create"),
    path("targets/<int:pk>/", views.target_detail, name="target_detail"),
    path("targets/<int:pk>/edit/", views.target_edit, name="target_edit"),
    path("targets/<int:pk>/delete/", views.target_delete, name="target_delete"),
    path("unified-log/", views.unified_log_root, name="unified_log_root"),
    path("unified-log/<str:tab>/", views.unified_log, name="unified_log"),

    # Engineering & Maintenance
    path("maintenance/tickets/", views.ticket_list, name="ticket_list"),
    path("maintenance/tickets/create/", views.ticket_create, name="ticket_create"),
    path("maintenance/tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("maintenance/tickets/<int:pk>/resolve/", views.ticket_resolve, name="ticket_resolve"),
    path("maintenance/calibrations/", views.calibration_list, name="calibration_list"),
    path("maintenance/calibrations/create/", views.calibration_create, name="calibration_create"),
    path("maintenance/calibrations/<int:pk>/status/", views.calibration_status_update, name="calibration_status_update"),

    # Plate Solver
    path("platesolver/", views.platesolver_index, name="platesolver_index"),
    path("platesolver/api/field/", views.platesolver_api_field, name="platesolver_api_field"),
    path("platesolver/api/field/", views.platesolver_api_field, name="api_get_field"),
    path("platesolver/api/solve/", views.platesolver_api_solve, name="platesolver_api_solve"),
    path("platesolver/api/solve/", views.platesolver_api_solve, name="api_solve_field"),
    path("platesolver/api/sync/", views.platesolver_api_sync, name="platesolver_api_sync"),
    path("platesolver/api/sync/", views.platesolver_api_sync, name="api_sync_telescope"),

    # Feedback & Notifications
    path("feedback/", views.feedback_view, name="feedback"),
    path("feedback/<int:pk>/respond/", views.feedback_respond_view, name="feedback_respond"),
    path("notifications/read/", views.mark_notifications_read, name="mark_notifications_read"),

    # TCS User Management (TCS_ADMIN / TCS_MEMBER)
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),

    # Legacy routes for compatibility
    path("<int:pk>/", views.telescope_detail, name="detail"),
    path("create/", views.telescope_create, name="create"),
    path("<int:pk>/edit/", views.telescope_edit, name="edit"),
    path("<int:pk>/delete/", views.telescope_delete, name="delete"),
]
