from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser
from products.models import Product

from .models import StockEntry

User = get_user_model()


class StockEntryAPITest(APITestCase):
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

    def test_create_stock_in_entry(self):
        url = reverse("stock-in-api")  # Assuming router or name is stockin-list
        data = {
            "product": self.product.id,
            "quantity": 10,
            "entry_type": "in",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StockEntry.objects.count(), 1)
        self.assertEqual(StockEntry.objects.get().entry_type, "in")

    def test_list_stock_in_entries(self):
        StockEntry.objects.create(
            product=self.product, quantity=5, entry_type="in", created_by=self.inv_user
        )
        url = reverse("stock-in-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
