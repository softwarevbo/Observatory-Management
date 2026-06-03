from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .models import Telescope

class TelescopeModelTests(TestCase):
    def test_telescope_creation(self):
        tele = Telescope.objects.create(
            id_name="test_mount",
            name="Test Mount Telescope",
            aperture="0.5 Meter",
            type="Reflector",
            status="idle"
        )
        self.assertEqual(str(tele), "Test Mount Telescope")
        self.assertEqual(tele.id_name, "test_mount")

class TelescopeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.super_user = User.objects.create_superuser(
            username="super_admin",
            email="super@vbo.res.in",
            password="pass"
        )
        self.tele_admin = User.objects.create_user(
            username="tele_admin",
            email="admin@vbo.res.in",
            password="pass",
            can_access_telescope=True,
            is_telescope_admin=True
        )
        self.tele_operator = User.objects.create_user(
            username="operator",
            email="operator@vbo.res.in",
            password="pass",
            can_access_telescope=True,
            is_telescope_admin=False
        )
        self.pm_user = User.objects.create_user(
            username="pm_user",
            email="pm@vbo.res.in",
            password="pass",
            can_access_pm=True,
            can_access_telescope=False
        )

    def test_unauthenticated_redirect(self):
        response = self.client.get(reverse("telescope:dashboard"))
        self.assertRedirects(response, "/accounts/login/?next=/telescope/")

    def test_unauthorized_telescope_user(self):
        self.client.login(username="pm_user", password="pass")
        response = self.client.get(reverse("telescope:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response.url)

    def test_authorized_dashboard(self):
        self.client.login(username="operator", password="pass")
        response = self.client.get(reverse("telescope:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Default telescopes should be pre-populated
        self.assertTrue(Telescope.objects.filter(id_name="vbt_234").exists())
        self.assertContains(response, "Vainu Bappu Telescope (VBT)")

    def test_telescope_detail_view(self):
        self.client.login(username="operator", password="pass")
        # Initialize default telescopes
        self.client.get(reverse("telescope:dashboard"))
        vbt = Telescope.objects.get(id_name="vbt_234")
        
        response = self.client.get(reverse("telescope:detail", args=[vbt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Telescope Description")

    def test_admin_crud_access(self):
        # Operator cannot create
        self.client.login(username="operator", password="pass")
        response = self.client.get(reverse("telescope:create"))
        self.assertRedirects(response, reverse("telescope:dashboard"))
        
        # Tele admin can get create page
        self.client.login(username="tele_admin", password="pass")
        response = self.client.get(reverse("telescope:create"))
        self.assertEqual(response.status_code, 200)

        # Tele admin creates a telescope
        post_data = {
            "name": "Custom 60cm Refractor",
            "aperture": "0.6 Meter",
            "type": "Refractor",
            "status": "idle",
            "current_target": "None",
            "ra": "12h 00m 00s",
            "dec": "+15° 00′ 00″",
            "dome": "Closed",
            "focus": "Prime Focus",
            "instrument": "None",
            "ccd_temp": "Ambient",
            "tracking": "Disabled",
            "description": "Custom testing telescope description",
            "history": "Inaugurated recently."
        }
        response = self.client.post(reverse("telescope:create"), post_data)
        self.assertRedirects(response, reverse("telescope:dashboard"))
        
        tele = Telescope.objects.get(name="Custom 60cm Refractor")
        self.assertEqual(tele.id_name, "custom_60cm_refractor")

        # Tele admin edits the telescope
        edit_data = post_data.copy()
        edit_data["status"] = "observing"
        edit_data["current_target"] = "Mars"
        response = self.client.post(reverse("telescope:edit", args=[tele.pk]), edit_data)
        self.assertRedirects(response, reverse("telescope:dashboard"))
        
        tele.refresh_from_db()
        self.assertEqual(tele.status, "observing")
        self.assertEqual(tele.current_target, "Mars")

        # Tele admin deletes the telescope
        response = self.client.get(reverse("telescope:delete", args=[tele.pk]))
        self.assertRedirects(response, reverse("telescope:dashboard"))
        self.assertFalse(Telescope.objects.filter(pk=tele.pk).exists())
