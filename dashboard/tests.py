from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser

User = get_user_model()

"""
This module contains test cases validating dashboard views, API endpoints,
and session parameter boundaries.
"""

class DashboardAPITest(APITestCase):
    """
    Test suite validating the Inventory Dashboard APIs and Overview rendering.
    """
    def setUp(self):
        # Create standard user profile
        self.user = User.objects.create_user(username="testuser", password="testpass")
        
        # Create inventory-specific user profile
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="admin"
        )
        self.inv_user.set_password("testpass")
        
        # Initialize APIClient and authenticate
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        
        # Setup session variables matching InventoryAccessMiddleware session hooks
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save()

    def test_dashboard_overview(self):
        """
        Validates that retrieving the dashboard overview returns 200 OK
        and injects required KPI fields in the view template context.
        """
        url = reverse("dashboard-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_products", response.context)
        self.assertIn("total_stock", response.context)
