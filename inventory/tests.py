from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from products.models import Product

from .models import InventoryAdjustment, InventoryUser, SerialNumber

"""
This module contains unit tests validating the Inventory REST API controllers.
"""

User = get_user_model()


class InventoryAPITest(APITestCase):
    """Test suite validating inventory adjustments and serial numbers creation and listing APIs."""

    def setUp(self):
        # Create regular Django user and authenticate
        self.user = User.objects.create_user(username="testuser", password="testpass")
        
        # Create separate InventoryUser instance and simulate session registration
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="super_admin"
        )
        self.inv_user.set_password("testpass")
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        
        # Configure middleware requirements using session ID
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save()
        self.product = Product.objects.create(name="Test Product", sku="TP001")

    def test_create_inventory_adjustment(self):
        """Verifies that the adjustments API successfully tracks a manual adjustment entry."""
        url = reverse("inventory-adjustments-api")
        data = {
            "product_id": self.product.id,
            "adjustment_type": "manual",
            "quantity": 5,
            "reason": "Test adjustment",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(InventoryAdjustment.objects.count(), 1)

    def test_list_inventory_adjustments(self):
        """Verifies that the adjustments API correctly lists historical adjustment logs."""
        InventoryAdjustment.objects.create(
            product=self.product,
            adjustment_type="manual",
            quantity=3,
            created_by=self.inv_user,
        )
        url = reverse("inventory-adjustments-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_serial_number(self):
        """Verifies that the serial numbers API records new serial number items."""
        url = reverse("inventory-serials-api")
        data = {
            "serial_number": "SN123456",
            "product_id": self.product.id,
            "status": "available",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SerialNumber.objects.count(), 1)

    def test_list_serial_numbers(self):
        """Verifies that the serial numbers API lists registered serials with pagination."""
        SerialNumber.objects.create(serial_number="SN0001", product=self.product)
        url = reverse("inventory-serials-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_super_admin_can_access_db_backup(self):
        """Verifies that a Super Admin can successfully access the DB Backup/Restore page."""
        url = reverse("inventory_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_branch_admin_cannot_access_db_backup(self):
        """Verifies that a Branch Admin is blocked from accessing the DB Backup/Restore page."""
        branch_admin = InventoryUser.objects.create(
            username="branchadmin", is_active=True, role="branch_admin"
        )
        branch_admin.set_password("testpass")
        
        session = self.client.session
        session["inv_user_id"] = branch_admin.id
        session.save()
        
        url = reverse("inventory_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)


import json

class InventoryChatAPITest(APITestCase):
    """Test suite validating inventory chat API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.inv_user1 = InventoryUser.objects.create(
            username="testuser1", is_active=True, role="super_admin"
        )
        self.inv_user2 = InventoryUser.objects.create(
            username="testuser2", is_active=True, role="staff"
        )
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        
        session = self.client.session
        session["inv_user_id"] = self.inv_user1.id
        session.save()

    def test_inv_chat_users_list(self):
        """Verifies that the users list endpoint returns active inventory users and unread counts."""
        url = reverse("inv-chat-users")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["contacts"]), 1)
        self.assertEqual(data["contacts"][0]["username"], "testuser2")

    def test_inv_chat_send_and_retrieve_messages(self):
        """Verifies sending and retrieving messages between inventory users."""
        url_send = reverse("inv-chat-send", kwargs={"user_id": self.inv_user2.id})
        response = self.client.post(url_send, {"content": "Hello user2"}, format="json")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["content"], "Hello user2")

        # Now retrieve messages
        url_messages = reverse("inv-chat-messages", kwargs={"user_id": self.inv_user2.id})
        response = self.client.get(url_messages)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["content"], "Hello user2")
        self.assertTrue(data["messages"][0]["is_mine"])

    def test_inv_chat_poll(self):
        """Verifies the polling endpoint returns new messages correctly."""
        from .models import InventoryMessage
        # Create a message from user 2 to user 1
        msg = InventoryMessage.objects.create(
            sender=self.inv_user2,
            recipient=self.inv_user1,
            content="Polling message"
        )

        url_poll = reverse("inv-chat-poll", kwargs={"user_id": self.inv_user2.id})
        # Poll without after_id
        response = self.client.get(url_poll)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["id"], msg.id)

        # Poll with after_id equal to msg.id (no new messages)
        response = self.client.get(url_poll, {"after_id": msg.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 0)

