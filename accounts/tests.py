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
        
        # Check that the user still exists in the database but is deactivated
        self.tele_user.refresh_from_db()
        self.assertFalse(self.tele_user.is_active)


class UserFormPermissionsTest(TestCase):
    """
    Test case to verify that System Access Permissions and Inventory Branch fields
    are completely removed from the standard User forms and default correctly.
    """

    def test_user_create_form_fields(self):
        from accounts.forms import UserCreateForm
        form = UserCreateForm()
        self.assertNotIn("can_access_pm", form.fields)
        self.assertNotIn("can_access_inventory", form.fields)
        self.assertNotIn("can_access_telescope", form.fields)
        self.assertNotIn("inventory_branch", form.fields)

    def test_user_edit_form_fields(self):
        from accounts.forms import UserEditForm
        form = UserEditForm()
        self.assertNotIn("can_access_pm", form.fields)
        self.assertNotIn("can_access_inventory", form.fields)
        self.assertNotIn("can_access_telescope", form.fields)
        self.assertNotIn("inventory_branch", form.fields)

    def test_user_creation_defaults(self):
        from accounts.forms import UserCreateForm
        data = {
            "username": "new_pm_user",
            "first_name": "PM",
            "last_name": "User",
            "email": "pm@example.com",
            "role": "member",
            "team": "software",
            "avatar_color": "#6366f1",
            "password1": "pass@1234",
            "password2": "pass@1234",
        }
        form = UserCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.can_access_pm)
        self.assertFalse(user.can_access_inventory)
        self.assertFalse(user.can_access_telescope)
        self.assertIsNone(user.inventory_branch)


class UserPortalIsolationTest(TestCase):
    """
    Test case to verify that user isolation and dynamic routing work correctly
    for telescope-only users vs project management users.
    """

    def setUp(self):
        # Create standard PM user
        self.pm_user = User.objects.create_user(
            username="pmuser",
            email="pm@example.com",
            password="pass@1234",
            can_access_pm=True,
            can_access_telescope=False,
            avatar_color="#6366f1",
        )
        # Create Telescope-only user
        self.tele_user = User.objects.create_user(
            username="teleuser",
            email="tele@example.com",
            password="pass@1234",
            can_access_pm=False,
            can_access_telescope=True,
            avatar_color="#8b5cf6",
        )

    def test_pm_user_root_redirect(self):
        self.client.login(username="pmuser", password="pass@1234")
        response = self.client.get("/")
        self.assertRedirects(response, reverse("tasks:dashboard"))

    def test_tele_user_root_redirect(self):
        self.client.login(username="teleuser", password="pass@1234")
        response = self.client.get("/")
        self.assertRedirects(response, reverse("telescope:dashboard"))

    def test_tele_user_restricted_from_pm(self):
        self.client.login(username="teleuser", password="pass@1234")
        # Try to access a PM page like the dashboard
        response = self.client.get(reverse("tasks:dashboard"))
        # Expect redirect to the telescope dashboard
        self.assertRedirects(response, reverse("telescope:dashboard"))

    def test_tele_user_login_page_redirect(self):
        self.client.login(username="teleuser", password="pass@1234")
        # Access the standard login page while logged in
        response = self.client.get(reverse("accounts:login"))
        # Expect redirect to the telescope dashboard
        self.assertRedirects(response, reverse("telescope:dashboard"))


class GlobalUsernameUniquenessTest(TestCase):
    """
    Test case to verify username uniqueness constraints are enforced across both
    standard User and InventoryUser models.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from inventory.models import InventoryUser
        User = get_user_model()
        # Create standard PM user
        self.pm_user = User.objects.create_user(
            username="clashinguser",
            email="pm@example.com",
            password="pass@1234",
            can_access_pm=True,
            can_access_telescope=False,
            avatar_color="#6366f1",
        )
        # Create Inventory user
        self.inv_user = InventoryUser.objects.create(
            username="invclash",
            email="inv@example.com",
            role="staff",
            is_active=True,
        )
        self.inv_user.set_password("pass@1234")

    def test_standard_user_creation_clash_with_inventory(self):
        from accounts.forms import UserCreateForm
        data = {
            "username": "invclash",  # Clashes with existing Inventory user
            "first_name": "New",
            "last_name": "User",
            "email": "new@example.com",
            "role": "member",
            "team": "software",
            "avatar_color": "#6366f1",
            "password1": "pass@1234",
            "password2": "pass@1234",
        }
        form = UserCreateForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertEqual(form.errors["username"][0], "This username is already taken.")

    def test_inventory_user_creation_clash_with_standard(self):
        from django.contrib.auth import get_user_model
        from inventory.models import InventoryUser
        User = get_user_model()
        # Simulate creating an inventory user with standard user's username
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass@1234")
        self.client.login(username="admin", password="pass@1234")
        
        url = reverse("accounts:inventory_user_create")
        data = {
            "username": "clashinguser",  # Clashes with PM user
            "email": "another@example.com",
            "password": "pass@1234",
            "role": "staff",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, "/accounts/users/?tab=inventory")
        
        # Verify it was not created
        self.assertFalse(InventoryUser.objects.filter(username="clashinguser").exists())

    def test_telescope_user_creation_clash_with_inventory(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass@1234")
        self.client.login(username="admin", password="pass@1234")
        
        url = reverse("accounts:telescope_user_create")
        data = {
            "username": "invclash",  # Clashes with Inventory user
            "email": "another@example.com",
            "password": "pass@1234",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, "/accounts/users/?tab=telescope")
        
        # Verify standard User was not created with this username
        self.assertFalse(User.objects.filter(username="invclash").exists())


class UserAdminTest(TestCase):
    """
    Test case to verify custom UserAdmin functionality (e.g. badges, querysets).
    """

    def test_badges(self):
        from django.contrib.admin.sites import AdminSite
        from accounts.admin import UserAdmin
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123",
            role="admin",
            is_active=True,
            is_superuser=True
        )
        site = AdminSite()
        admin_instance = UserAdmin(User, site)
        
        # Test role_badge
        role_html = admin_instance.role_badge(user)
        self.assertIn("Admin", role_html)
        
        # Test status_badge
        status_html = admin_instance.status_badge(user)
        self.assertIn("Active", status_html)
        
        # Test is_superuser_badge
        superuser_html = admin_instance.is_superuser_badge(user)
        self.assertIn("Yes", superuser_html)




