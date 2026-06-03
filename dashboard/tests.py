from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser

User = get_user_model()


class DashboardAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="admin"
        )
        self.inv_user.set_password("testpass")
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save()

    def test_dashboard_overview(self):
        url = reverse("dashboard-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_products", response.context)
        self.assertIn("total_stock", response.context)
