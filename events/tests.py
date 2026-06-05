from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch

from tasks.models import Project, Task
from events.models import CalendarEvent, UserCalendarSettings
from events.forms import CalendarEventForm

User = get_user_model()

"""
This module contains unit tests validating the events application lifecycle.
Specifically:
1. post_save and post_delete signal synchronizations.
2. Form dynamic query filtering.
"""

class CalendarSignalsAndFormTests(TestCase):
    """
    Test suite validating calendar signals, forms, and mock sync behaviors.
    """
    def setUp(self):
        # Create standard test user profile
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
            role="project_manager",
            is_active=True
        )
        
        # Create test project
        self.project = Project.objects.create(
            name="Test Project",
            created_by=self.user,
            project_incharge=self.user,
            visibility="public"
        )
        self.project.managers.add(self.user)
        
        # Create test task
        self.task = Task.objects.create(
            title="Test Task",
            project=self.project,
            created_by=self.user
        )
        
        # Setup sync configuration parameters
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
        """
        Validates that creating or updating a calendar event triggers external calendar sync hooks.
        """
        # Create a calendar event
        event = CalendarEvent.objects.create(
            title="Meeting Title",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            created_by=self.user,
            project=self.project
        )
        
        # Verify sync signals are triggered upon creation
        mock_sync_google.assert_called_once_with(event)
        mock_sync_caldav.assert_called_once_with(event)

        # Reset mock call counters
        mock_sync_google.reset_mock()
        mock_sync_caldav.reset_mock()

        # Update event attributes
        event.title = "Updated Meeting Title"
        event.save()

        # Verify sync signals are triggered upon update
        mock_sync_google.assert_called_once_with(event)
        mock_sync_caldav.assert_called_once_with(event)

    @patch('events.signals.delete_from_external_calendars')
    def test_calendar_event_delete_signal(self, mock_delete_external):
        """
        Validates that deleting a calendar event triggers cleanup methods for external platforms.
        """
        # Create an event
        event = CalendarEvent.objects.create(
            title="Meeting Title",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            created_by=self.user,
            project=self.project
        )
        
        # Delete event record
        event.delete()

        # Verify delete signal was dispatched to cleanup methods
        mock_delete_external.assert_called_once_with(event)

    def test_calendar_event_form_dynamic_queryset(self):
        """
        Validates that tasks list options are dynamically filtered to match the selected project in forms.
        """
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
        
        # Instantiate form with POST data and active user context
        form = CalendarEventForm(data=data, user=self.user)
        
        # Verify choices list includes project tasks and validates form fields successfully
        self.assertIn(self.task, form.fields["task"].queryset)
        self.assertTrue(form.is_valid(), form.errors)
