from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch

from tasks.models import Project, Task
from events.models import CalendarEvent, UserCalendarSettings
from events.forms import CalendarEventForm

User = get_user_model()

class CalendarSignalsAndFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
            role="project_manager",
            is_active=True
        )
        self.project = Project.objects.create(
            name="Test Project",
            created_by=self.user,
            project_incharge=self.user,
            visibility="public"
        )
        self.project.managers.add(self.user)
        self.task = Task.objects.create(
            title="Test Task",
            project=self.project,
            created_by=self.user
        )
        # Create user settings for calendar sync
        self.settings = UserCalendarSettings.objects.create(
            user=self.user,
            is_google_synced=True,
            is_caldav_synced=True,
            caldav_url="http://localhost:5232/",
            caldav_user="testuser",
            caldav_password="password"
        )

    @patch('events.signals.sync_event_to_google')
    @patch('events.signals.sync_event_to_caldav')
    def test_calendar_event_save_signals(self, mock_sync_caldav, mock_sync_google):
        # Create an event
        event = CalendarEvent.objects.create(
            title="Meeting Title",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            created_by=self.user,
            project=self.project
        )
        
        # Verify sync signals were called
        mock_sync_google.assert_called_once_with(event)
        mock_sync_caldav.assert_called_once_with(event)

        # Reset mock calls
        mock_sync_google.reset_mock()
        mock_sync_caldav.reset_mock()

        # Update event
        event.title = "Updated Meeting Title"
        event.save()

        # Verify sync signals were called again
        mock_sync_google.assert_called_once_with(event)
        mock_sync_caldav.assert_called_once_with(event)

    @patch('events.signals.delete_from_external_calendars')
    def test_calendar_event_delete_signal(self, mock_delete_external):
        # Create an event
        event = CalendarEvent.objects.create(
            title="Meeting Title",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            created_by=self.user,
            project=self.project
        )
        
        # Delete the event
        event.delete()

        # Verify delete signal was called
        mock_delete_external.assert_called_once_with(event)

    def test_calendar_event_form_dynamic_queryset(self):
        # Test that task queryset resolves correctly when project is provided in self.data (POST data)
        data = {
            "title": "New Event",
            "description": "Event description",
            "event_type": "meeting",
            "project": self.project.id,
            "task": self.task.id,
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "end_datetime": (timezone.now() + timezone.timedelta(days=1, hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "color": "#6366f1",
        }
        
        # Instantiate form with data and user
        form = CalendarEventForm(data=data, user=self.user)
        
        # Check task field queryset has task
        self.assertIn(self.task, form.fields["task"].queryset)
        self.assertTrue(form.is_valid(), form.errors)
