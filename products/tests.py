from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from inventory.models import InventoryUser

from .models import Category, Product

User = get_user_model()


class ProductsAPITest(APITestCase):
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
        self.category = Category.objects.create(name="Test Category")

    def test_create_category(self):
        url = reverse("categories-api")
        data = {
            "name": "New Category",
            "description": "Category description",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_list_categories(self):
        url = reverse("categories-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_product(self):
        url = reverse("products-api")
        data = {
            "name": "New Product",
            "category": self.category.id,
            "sku": "NP001",
            "price": "9.99",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)

    def test_list_products(self):
        Product.objects.create(
            name="Existing Product", category=self.category, sku="EP001", price=5.00
        )
        url = reverse("products-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
