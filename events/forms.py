from django import forms
from django.utils import timezone
from accounts.models import User
from tasks.models import Project, Task
from .models import CalendarEvent

"""
This module defines the ModelForm for calendar events creation and editing.
It incorporates dynamic project/task choice query parameters filtering and start/end time validations.
"""

class CalendarEventForm(forms.ModelForm):
    """
    Form used to schedule and modify calendar event entries.
    """
    class Meta:
        model = CalendarEvent
        fields = [
            "title",
            "description",
            "event_type",
            "project",
            "task",
            "location",
            "start_datetime",
            "end_datetime",
            "attendees",
            "meeting_link",
            "meeting_password",
            "color",
        ]
        # Custom HTML widget overrides for interactive styling
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "project": forms.Select(attrs={"class": "form-control", "id": "id_event_project"}),
            "task": forms.Select(attrs={"class": "form-control", "id": "id_event_task"}),
            "location": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Physical location (optional)"}
            ),
            "start_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "end_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            # Renders checklist options for selecting multiple attendee users
            "attendees": forms.CheckboxSelectMultiple(),
            "meeting_link": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "Meeting URL (optional)"}
            ),
            "meeting_password": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Meeting Password (optional)",
                }
            ),
            "color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Dynamically filters project and task dropdown choice lists based on user authorizations.
        """
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["project"].empty_label = "— No project —"
        self.fields["project"].required = False
        self.fields["task"].empty_label = "— No task —"
        self.fields["task"].required = False
        
        if user:
            from django.db.models import Q
            
            # Admins can see all projects; PMs/Members can only link events to their visible projects
            if user.is_admin:
                projects_qs = Project.objects.all()
            else:
                projects_qs = Project.objects.filter(
                    Q(visibility="public") | Q(managers=user) | Q(members=user)
                ).distinct()
            
            self.fields["project"].queryset = projects_qs
            
            # Handle dependent cascading query filtering:
            # Task queryset resolves to untrashed tasks belonging strictly to the selected project
            project_id = None
            if self.instance and self.instance.project_id:
                project_id = self.instance.project_id
            elif self.data and self.data.get("project"):
                try:
                    project_id = int(self.data.get("project"))
                except (ValueError, TypeError):
                    pass
            
            if project_id:
                self.fields["task"].queryset = Task.objects.filter(
                    project_id=project_id, is_in_trash=False
                ).exclude(linked_bugs__is_in_trash=True)
            else:
                self.fields["task"].queryset = Task.objects.none()

        # Restrict attendees selection to active system users only
        self.fields["attendees"].queryset = User.objects.filter(
            is_active=True
        ).order_by("first_name")
        self.fields["attendees"].required = False

    def clean(self):
        """
        Validates calendar date ranges:
        - End time must occur after start time.
        - Start time cannot be scheduled in the past on new events creation.
        """
        cleaned_data = super().clean()
        start, end = cleaned_data.get("start_datetime"), cleaned_data.get(
            "end_datetime"
        )
        if start and end:
            if start >= end:
                raise forms.ValidationError("End time must be after start time.")
            # Verify event start time isn't in the past on initial creation (with a 5 min tolerance)
            if not self.instance.pk and start < (
                timezone.now() - timezone.timedelta(minutes=5)
            ):
                raise forms.ValidationError("Event cannot start in the past.")
        return cleaned_data
