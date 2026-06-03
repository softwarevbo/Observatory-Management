from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser

from .models import AuditLog

User = get_user_model()


class AuditAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass", role="admin"
        )
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="super_admin"
        )
        self.inv_user.set_password("testpass")
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save()
        self.log = AuditLog.objects.create(
            user=self.inv_user,
            action="Test action",
            model_name="TestModel",
            object_id=1,
            changes="{}",
        )

    def test_list_audit_logs(self):
        url = reverse("audit-logs")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.context["logs"]), 1)
