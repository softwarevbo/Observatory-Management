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
