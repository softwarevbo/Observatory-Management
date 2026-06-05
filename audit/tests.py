from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser

from .models import AuditLog

# Fetch the active custom User model
User = get_user_model()

"""
This module contains integration tests for the audit application.
It uses DRF's `APITestCase` which extends Django's default test runner 
to supply helper attributes like `APIClient` and custom REST assertions.
"""

class AuditAPITest(APITestCase):
    """
    Test suite verifying access and rendering behavior of the audit logs page.
    """

    def setUp(self):
        """
        Runs before each test method to populate mock users, sessions, and log instances.
        """
        # 1. Create a mock administrator user
        self.user = User.objects.create_user(
            username="testuser", password="testpass", role="admin"
        )
        
        # 2. Create a mock inventory user
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="super_admin"
        )
        self.inv_user.set_password("testpass")
        
        # 3. Instantiate the DRF API Test Client
        self.client = APIClient()
        
        # 4. Perform client session log in
        self.client.login(username="testuser", password="testpass")
        
        # 5. Inject the inventory user ID directly into the client's session.
        # This mocks the session logic used by the inventory portal middleware.
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save() # Saves the session context changes in memory
        
        # 6. Create a mock audit log entry to query in list tests
        self.log = AuditLog.objects.create(
            user=self.inv_user,
            action="Test action",
            model_name="TestModel",
            object_id=1,
            changes="{}",
        )

    def test_list_audit_logs(self):
        """
        Tests that requesting the audit logs list page returns a 200 status code
        and correctly lists the mock logs in the context variables.
        """
        # Resolve path pattern name
        url = reverse("audit-logs")
        
        # Trigger GET request
        response = self.client.get(url)
        
        # Verify response code is OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the logs are included in the view context variables
        self.assertGreaterEqual(len(response.context["logs"]), 1)
