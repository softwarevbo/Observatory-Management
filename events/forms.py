from django import forms
from django.utils import timezone
from accounts.models import User
from tasks.models import Project, Task
from .models import CalendarEvent


class CalendarEventForm(forms.ModelForm):
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
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["project"].empty_label = "— No project —"
        self.fields["project"].required = False
        self.fields["task"].empty_label = "— No task —"
        self.fields["task"].required = False
        
        if user:
            from django.db.models import Q
            
            if user.is_admin:
                projects_qs = Project.objects.all()
            else:
                projects_qs = Project.objects.filter(
                    Q(visibility="public") | Q(managers=user) | Q(members=user)
                ).distinct()
            
            self.fields["project"].queryset = projects_qs
            
            if self.instance and self.instance.project:
                self.fields["task"].queryset = Task.objects.filter(project=self.instance.project, is_in_trash=False)
            else:
                self.fields["task"].queryset = Task.objects.none()

        self.fields["attendees"].queryset = User.objects.filter(
            is_active=True
        ).order_by("first_name")
        self.fields["attendees"].required = False

    def clean(self):
        cleaned_data = super().clean()
        start, end = cleaned_data.get("start_datetime"), cleaned_data.get(
            "end_datetime"
        )
        if start and end:
            if start >= end:
                raise forms.ValidationError("End time must be after start time.")
            if not self.instance.pk and start < (
                timezone.now() - timezone.timedelta(minutes=5)
            ):
                raise forms.ValidationError("Event cannot start in the past.")
        return cleaned_data
