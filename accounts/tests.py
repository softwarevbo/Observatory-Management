from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import User

class TelescopeUserManagementTest(TestCase):
    def setUp(self):
        # Create a superuser to access admin paths
        self.admin = User.objects.create_superuser(
            username="admin", 
            email="admin@observatory.res.in", 
            password="pass@1234"
        )
        self.client.login(username="admin", password="pass@1234")

        # Create an existing telescope user
        self.tele_user = User.objects.create_user(
            username="operator1",
            email="operator1@observatory.res.in",
            password="pass1234",
            can_access_telescope=True,
            can_operate_vbt=True
        )

    def test_user_list_telescope_tab(self):
        url = reverse("accounts:user_list") + "?tab=telescope"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "operator1")
        # Ensure VBT operators stats and other info is in context
        self.assertIn("stats", response.context)
        self.assertEqual(response.context["stats"]["vbt_operators"], 1)

    def test_telescope_user_create(self):
        url = reverse("accounts:telescope_user_create")
        data = {
            "username": "operator2",
            "email": "operator2@observatory.res.in",
            "password": "pass1234",
            "is_active": "on",
            "can_operate_vbt": "on",
            "can_operate_jcbt": "on",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        # Verify operator2 was created
        u = User.objects.get(username="operator2")
        self.assertTrue(u.can_access_telescope)
        self.assertTrue(u.can_operate_vbt)
        self.assertTrue(u.can_operate_jcbt)
        self.assertFalse(u.can_operate_zeiss)

    def test_telescope_user_edit(self):
        url = reverse("accounts:telescope_user_edit", args=[self.tele_user.pk])
        data = {
            "email": "updated_operator@observatory.res.in",
            "password": "", # Keep current password
            "can_operate_vbt": "on",
            "can_command_dome": "on",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        self.tele_user.refresh_from_db()
        self.assertEqual(self.tele_user.email, "updated_operator@observatory.res.in")
        self.assertTrue(self.tele_user.can_operate_vbt)
        self.assertTrue(self.tele_user.can_command_dome)
        self.assertFalse(self.tele_user.can_operate_jcbt)

    def test_telescope_user_toggle(self):
        self.assertTrue(self.tele_user.is_active)
        url = reverse("accounts:telescope_user_toggle", args=[self.tele_user.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        
        self.tele_user.refresh_from_db()
        self.assertFalse(self.tele_user.is_active)

    def test_telescope_user_delete(self):
        url = reverse("accounts:telescope_user_delete", args=[self.tele_user.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("accounts:user_list") + "?tab=telescope")
        self.assertFalse(User.objects.filter(pk=self.tele_user.pk).exists())
