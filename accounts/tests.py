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

        from telescope.models import TelescopeUser
        # 3. Create a mock standard user account in TelescopeUser for TCS testing.
        self.tele_user = TelescopeUser.objects.create_user(
            username="operator1",
            email="operator1@observatory.res.in",
            password="pass1234",
            can_operate_vbt=True
        )

    def test_user_list_telescope_tab(self):
        """
        Tests that an admin can view the TCS user list page.
        """
        url = reverse("telescope:user_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "operator1")

    def test_telescope_user_create(self):
        """
        Tests creating a new TCS user via form POST submission.
        """
        url = reverse("telescope:user_create")
        
        data = {
            "username": "operator2",
            "email": "operator2@observatory.res.in",
            "password1": "pass1234",
            "password2": "pass1234",
            "role": "observer",
        }
        
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("telescope:user_list"))
        
        from telescope.models import TelescopeUser
        u = TelescopeUser.objects.get(username="operator2")
        self.assertEqual(u.role, "observer")

    def test_telescope_user_edit(self):
        """
        Tests editing an existing TCS user via a POST request.
        """
        url = reverse("telescope:user_edit", args=[self.tele_user.pk])
        
        data = {
            "username": "operator1",
            "email": "updated_operator@observatory.res.in",
            "new_password": "",
            "role": "observer",
        }
        
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("telescope:user_list"))
        
        self.tele_user.refresh_from_db()
        self.assertEqual(self.tele_user.email, "updated_operator@observatory.res.in")

    def test_telescope_user_toggle(self):
        """
        Tests toggling the 'is_active' state of a TCS user.
        """
        self.assertTrue(self.tele_user.is_active)
        
        url = reverse("telescope:user_toggle", args=[self.tele_user.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("telescope:user_list"))
        
        self.tele_user.refresh_from_db()
        self.assertFalse(self.tele_user.is_active)

    def test_telescope_user_delete(self):
        """
        Tests deleting/deactivating a TCS user account.
        """
        url = reverse("telescope:user_delete", args=[self.tele_user.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("telescope:user_list"))
        
        from telescope.models import TelescopeUser
        self.assertFalse(TelescopeUser.objects.filter(pk=self.tele_user.pk).exists())


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
            "role": "PM_MEMBER",
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
        self.assertRedirects(response, reverse("telescope:user_list"))
        
        # Verify standard User was not created with this username
        self.assertFalse(User.objects.filter(username="invclash").exists())


class RBACTestCase(TestCase):
    """
    Comprehensive test case for Role-Based Access Control (RBAC):
    - 7 roles: ROOT, PM_ADMIN, PM_MEMBER, TM_ADMIN, TM_MEMBER, IM_ADMIN, IM_MEMBER
    - 3 login entry points
    - Strict URL access restrictions
    - Promotion prevention & user management rules
    """

    def setUp(self):
        # Create users for all 7 canonical roles
        self.root_user = User.objects.create_user(
            username="root_admin", password="password123", role="ROOT", is_superuser=True
        )
        self.pm_admin = User.objects.create_user(
            username="pm_admin", password="password123", role="PM_ADMIN"
        )
        self.pm_member = User.objects.create_user(
            username="pm_member", password="password123", role="PM_MEMBER"
        )
        self.tm_admin = User.objects.create_user(
            username="tm_admin", password="password123", role="TM_ADMIN"
        )
        self.tm_member = User.objects.create_user(
            username="tm_member", password="password123", role="TM_MEMBER"
        )
        self.im_admin = User.objects.create_user(
            username="im_admin", password="password123", role="IM_ADMIN"
        )
        self.im_member = User.objects.create_user(
            username="im_member", password="password123", role="IM_MEMBER"
        )

    def test_canonical_role_resolution(self):
        from accounts.rbac import get_canonical_role
        self.assertEqual(get_canonical_role(self.root_user), "ROOT")
        self.assertEqual(get_canonical_role(self.pm_admin), "PM_ADMIN")
        self.assertEqual(get_canonical_role(self.pm_member), "PM_MEMBER")
        self.assertEqual(get_canonical_role(self.tm_admin), "TCS_ADMIN")
        self.assertEqual(get_canonical_role(self.tm_member), "TCS_MEMBER")
        self.assertEqual(get_canonical_role(self.im_admin), "IM_ADMIN")
        self.assertEqual(get_canonical_role(self.im_member), "IM_MEMBER")

    def test_project_login_restrictions(self):
        url = reverse("accounts:login")

        # Allowed: ROOT, PM_ADMIN, PM_MEMBER
        res = self.client.post(url, {"username": "pm_admin", "password": "password123"})
        self.assertRedirects(res, reverse("tasks:dashboard"))
        self.client.logout()

        res = self.client.post(url, {"username": "root_admin", "password": "password123"})
        self.assertRedirects(res, reverse("tasks:dashboard"))
        self.client.logout()

        # Denied: TM_ADMIN, TM_MEMBER, IM_ADMIN, IM_MEMBER
        res = self.client.post(url, {"username": "tm_admin", "password": "password123"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Access Denied")

        res = self.client.post(url, {"username": "im_admin", "password": "password123"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Access Denied")

    def test_telescope_login_restrictions(self):
        url = reverse("accounts:telescope_login")

        # Allowed: ROOT, TM_ADMIN, TM_MEMBER
        res = self.client.post(url, {"username": "tm_admin", "password": "password123"})
        self.assertRedirects(res, "/telescopecontrol/")
        self.client.logout()

        res = self.client.post(url, {"username": "root_admin", "password": "password123"})
        self.assertRedirects(res, "/telescopecontrol/")
        self.client.logout()

        # Denied: PM_ADMIN, IM_ADMIN
        res = self.client.post(url, {"username": "pm_admin", "password": "password123"})
        self.assertRedirects(res, reverse("accounts:login"))

    def test_inventory_login_restrictions(self):
        url = reverse("accounts:inventory_login")

        # Allowed: ROOT, IM_ADMIN, IM_MEMBER
        res = self.client.post(url, {"username": "im_admin", "password": "password123"})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/inventorymanagement/dashboard/")
        self.client.logout()

        res = self.client.post(url, {"username": "root_admin", "password": "password123"})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/inventorymanagement/dashboard/")
        self.client.logout()



        # Denied: PM_ADMIN, TM_ADMIN
        res = self.client.post(url, {"username": "pm_admin", "password": "password123"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Access Denied")

    def test_url_access_isolation(self):
        # PM_MEMBER cannot access telescope or inventory
        self.client.login(username="pm_member", password="password123")
        res = self.client.get("/telescopecontrol/")
        self.assertRedirects(res, "/projectmanagement/dashboard/")

        res = self.client.get("/inventorymanagement/dashboard/")
        self.assertRedirects(res, "/projectmanagement/dashboard/")
        self.client.logout()

        # TM_MEMBER cannot access PM or inventory
        self.client.login(username="tm_member", password="password123")
        res = self.client.get("/projectmanagement/dashboard/")
        self.assertRedirects(res, "/telescopecontrol/")

        res = self.client.get("/inventorymanagement/dashboard/")
        self.assertRedirects(res, "/telescopecontrol/")
        self.client.logout()

        # IM_MEMBER cannot access PM or telescope
        self.client.login(username="im_member", password="password123")
        res = self.client.get("/projectmanagement/dashboard/")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/inventorymanagement/dashboard/")

        res = self.client.get("/telescopecontrol/")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/inventorymanagement/dashboard/")
        self.assertRedirects(res, "/inventorymanagement/dashboard/")
        self.client.logout()

    def test_promotion_prevention(self):
        from accounts.rbac import can_manage_target_user, can_assign_role

        # PM_ADMIN cannot manage TM_ADMIN or ROOT
        self.assertFalse(can_manage_target_user(self.pm_admin, self.root_user))
        self.assertFalse(can_manage_target_user(self.pm_admin, self.tm_admin))
        self.assertTrue(can_manage_target_user(self.pm_admin, self.pm_member))

        # PM_ADMIN cannot assign ROOT or TM_ADMIN
        self.assertFalse(can_assign_role(self.pm_admin, "ROOT"))
        self.assertFalse(can_assign_role(self.pm_admin, "TM_ADMIN"))
        self.assertTrue(can_assign_role(self.pm_admin, "PM_MEMBER"))

        # ROOT can assign any role
        self.assertTrue(can_assign_role(self.root_user, "PM_ADMIN"))
        self.assertTrue(can_assign_role(self.root_user, "TM_ADMIN"))
        self.assertTrue(can_assign_role(self.root_user, "IM_ADMIN"))

    def test_backup_export_access(self):
        url = reverse("accounts:export_backup")

        # Non-ROOT user access denied
        self.client.login(username="pm_member", password="password123")
        res = self.client.post(url, {"include_pm": "on"})
        self.assertEqual(res.status_code, 302)
        self.client.logout()

        # ROOT user can export backup zip
        self.client.login(username="root_admin", password="password123")
        res = self.client.post(url, {
            "include_pm": "on",
            "include_im": "on",
            "include_tcs": "on",
            "include_media": "on",
            "include_db": "on",
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/zip")
        self.client.logout()








