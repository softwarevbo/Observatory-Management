from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from products.models import Product

from .models import InventoryAdjustment, InventoryUser, SerialNumber

User = get_user_model()


class InventoryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.inv_user = InventoryUser.objects.create(
            username="testinvuser", is_active=True, role="super_admin"
        )
        self.inv_user.set_password("testpass")
        self.client = APIClient()
        self.client.login(username="testuser", password="testpass")
        session = self.client.session
        session["inv_user_id"] = self.inv_user.id
        session.save()
        self.product = Product.objects.create(name="Test Product", sku="TP001")

    def test_create_inventory_adjustment(self):
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
        SerialNumber.objects.create(serial_number="SN0001", product=self.product)
        url = reverse("inventory-serials-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
