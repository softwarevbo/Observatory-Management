from django import forms
from django.contrib import admin
from .models import (
    TelescopeUser, Telescope, TelescopeLog, TelescopeDiscussion, TelescopeDiscussionReply,
    Instrument, InstrumentSensor, TelemetryLog, FilterWheelConfig,
    ObservationTarget, ExposureRunLog, UnifiedLog,
    MaintenanceTicket, CalibrationLog,
    PlateSolveRun, SiteFeedback
)

"""
Django Admin registration for Telescope Control System (TCS) models.
"""


class TelescopeUserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Leave blank to keep current password"}
        ),
        required=False,
        help_text="Set or change password here.",
    )

    class Meta:
        model = TelescopeUser
        fields = "__all__"


@admin.register(TelescopeUser)
class TelescopeUserAdmin(admin.ModelAdmin):
    form = TelescopeUserForm
    list_display = (
        "username",
        "role",
        "email",
        "is_active",
        "is_telescope_admin",
        "created_at",
    )
    list_filter = ("role", "is_active", "is_telescope_admin")
    search_fields = ("username", "email")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get("password")
        if password:
            obj.set_password(password)
        super().save_model(request, obj, form, change)


@admin.register(Telescope)
class TelescopeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "id_name", "aperture", "status", "current_target")
    list_filter = ("status", "mount_type")
    search_fields = ("name", "code", "id_name", "current_target")


@admin.register(TelescopeLog)
class TelescopeLogAdmin(admin.ModelAdmin):
    list_display = ("telescope", "event_type", "message", "timestamp")
    list_filter = ("event_type", "telescope")
    search_fields = ("message",)


@admin.register(TelescopeDiscussion)
class TelescopeDiscussionAdmin(admin.ModelAdmin):
    list_display = ("title", "telescope", "user", "category", "is_pinned", "created_at")
    list_filter = ("category", "is_pinned", "telescope")
    search_fields = ("title", "content")


@admin.register(TelescopeDiscussionReply)
class TelescopeDiscussionReplyAdmin(admin.ModelAdmin):
    list_display = ("discussion", "user", "created_at")
    search_fields = ("message",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "instrument_type", "telescope", "status")
    list_filter = ("status", "instrument_type", "telescope")
    search_fields = ("name", "code")


@admin.register(InstrumentSensor)
class InstrumentSensorAdmin(admin.ModelAdmin):
    list_display = ("instrument", "sensor_name", "current_value", "unit")
    list_filter = ("instrument",)


@admin.register(TelemetryLog)
class TelemetryLogAdmin(admin.ModelAdmin):
    list_display = ("instrument", "sensor_name", "value", "unit", "status_flag", "timestamp")
    list_filter = ("status_flag", "instrument")


@admin.register(FilterWheelConfig)
class FilterWheelConfigAdmin(admin.ModelAdmin):
    list_display = ("instrument", "slot_number", "filter_name", "central_wavelength", "bandwidth")
    list_filter = ("instrument",)


@admin.register(ObservationTarget)
class ObservationTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "catalog_id", "object_class", "magnitude", "recommended_filter")
    list_filter = ("object_class",)
    search_fields = ("name", "catalog_id")


@admin.register(ExposureRunLog)
class ExposureRunLogAdmin(admin.ModelAdmin):
    list_display = ("target", "signal_to_noise", "sky_transparency", "started_at")
    list_filter = ("sky_transparency",)


@admin.register(UnifiedLog)
class UnifiedLogAdmin(admin.ModelAdmin):
    list_display = ("telescope", "date", "created_at")
    list_filter = ("telescope", "date")


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "status", "telescope", "instrument", "created_at")
    list_filter = ("severity", "status", "telescope", "instrument")
    search_fields = ("title", "description", "resolution_notes")


@admin.register(CalibrationLog)
class CalibrationLogAdmin(admin.ModelAdmin):
    list_display = ("instrument", "calibration_type", "status", "executed_at")
    list_filter = ("status", "calibration_type", "instrument")


@admin.register(PlateSolveRun)
class PlateSolveRunAdmin(admin.ModelAdmin):
    list_display = ("pk", "telescope", "status", "solved_ra_deg", "solved_dec_deg", "created_at")
    list_filter = ("status", "telescope")


@admin.register(SiteFeedback)
class SiteFeedbackAdmin(admin.ModelAdmin):
    list_display = ("subject", "category", "status", "name", "created_at")
    list_filter = ("category", "status")
    search_fields = ("subject", "message")
