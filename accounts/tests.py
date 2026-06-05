from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import User

"""
This module defines Unit Tests for testing accounts application features.
Django's test framework uses Python's standard unittest module structure.
Running tests executes operations on a separate isolated temporary database,
guaranteeing that test actions don't affect live/production data.
"""

class TelescopeUserManagementTest(TestCase):
    """
    Test case targeting Telescope-specific User creation, editing, deletion,
    and state toggles by an administrator.
    """

    def setUp(self):
        """
        setUp runs before every single test method.
        Use this to populate the temporary test database with initial mock objects 
        and set up the client session environment.
        """
        # 1. Create a superuser in the test database
        self.admin = User.objects.create_superuser(
            username="admin", 
            email="admin@observatory.res.in", 
            password="pass@1234"
        )
        
        # 2. Use the built-in Django Test Client to simulate a logged-in administrator session.
        # This will attach the admin session cookies to all future requests made during tests.
        self.client.login(username="admin", password="pass@1234")

        # 3. Create a mock standard user account with Telescope access permissions for modification tests.
        self.tele_user = User.objects.create_user(
            username="operator1",
            email="operator1@observatory.res.in",
            password="pass1234",
            can_access_telescope=True,
            can_operate_vbt=True
        )

    def test_user_list_telescope_tab(self):
        """
        Tests that an admin can view the user list page specifically filtered for Telescope users.
        """
        # Resolve the URL path name to '/accounts/users/?tab=telescope' dynamically
        url = reverse("accounts:user_list") + "?tab=telescope"
        
        # Send a GET request as the logged-in admin user
        response = self.client.get(url)
        
        # Assertions to verify correct response code and content
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "operator1") # Expect user list page contains the operator
        
        # Ensure stats dictionary (for rendering operator count summaries) is computed and present in context
        self.assertIn("stats", response.context)
        self.assertEqual(response.context["stats"]["vbt_operators"], 1)

    def test_telescope_user_create(self):
        """
        Tests creating a new telescope user via form POST submission.
        """
        url = reverse("accounts:telescope_user_create")
        
        # Form inputs representing new operator credentials and permissions
        data = {
            "username": "operator2",
            "email": "operator2@observatory.res.in",
            "password": "pass1234",
            "is_active": "on",
            "can_operate_vbt": "on",
            "can_operate_jcbt": "on",
        }
        
        # Send a POST request to submit the form data
        response = self.client.post(url, data)
        
        # Assert that the view redirects the admin user back to the list page on success
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        # Query the database to verify the user was actually saved and has correct attributes
        u = User.objects.get(username="operator2")
        self.assertTrue(u.can_access_telescope)
        self.assertTrue(u.can_operate_vbt)
        self.assertTrue(u.can_operate_jcbt)
        # Undefined checkboxes on POST fall back to False (e.g. Zeiss)
        self.assertFalse(u.can_operate_zeiss)

    def test_telescope_user_edit(self):
        """
        Tests editing an existing telescope user's fields via a POST request.
        """
        url = reverse("accounts:telescope_user_edit", args=[self.tele_user.pk])
        
        # Form parameters to change email and add dome command capabilities
        data = {
            "email": "updated_operator@observatory.res.in",
            "password": "", # Sending empty password should keep the current password unmodified
            "can_operate_vbt": "on",
            "can_command_dome": "on",
        }
        
        # Submit the edit request
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        # Reload the user object attributes from the database to get fresh updates
        self.tele_user.refresh_from_db()
        
        # Assert edits were updated correctly
        self.assertEqual(self.tele_user.email, "updated_operator@observatory.res.in")
        self.assertTrue(self.tele_user.can_operate_vbt)
        self.assertTrue(self.tele_user.can_command_dome)
        self.assertFalse(self.tele_user.can_operate_jcbt) # Ensure it was unchecked/disabled

    def test_telescope_user_toggle(self):
        """
        Tests toggling the 'is_active' state of a telescope operator.
        """
        # Ensure user starts active
        self.assertTrue(self.tele_user.is_active)
        
        url = reverse("accounts:telescope_user_toggle", args=[self.tele_user.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        # Refresh and verify is_active was toggled from True to False
        self.tele_user.refresh_from_db()
        self.assertFalse(self.tele_user.is_active)

    def test_telescope_user_delete(self):
        """
        Tests deleting a telescope operator account.
        """
        url = reverse("accounts:telescope_user_delete", args=[self.tele_user.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        # Check that the user no longer exists in the database
        self.assertFalse(User.objects.filter(pk=self.tele_user.pk).exists())
