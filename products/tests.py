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
            "serial_number": "SN-NEW-123",
            "model_number": "MN-880",
            "description": "Product description",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)

    def test_list_products(self):
        Product.objects.create(
            name="Existing Product", 
            category=self.category, 
            sku="EP001", 
            serial_number="SN-EXIST-456", 
            model_number="MN-500",
            description="Another product description",
        )
        url = reverse("products-api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_bulk_delete_products_as_super_admin(self):
        """Verifies that a Super Admin can bulk delete multiple selected products."""
        p1 = Product.objects.create(name="Product 1", sku="P001", category=self.category)
        p2 = Product.objects.create(name="Product 2", sku="P002", category=self.category)
        p3 = Product.objects.create(name="Product 3", sku="P003", category=self.category)
        
        url = reverse("bulk-delete-products")
        data = {
            "product_ids": [p1.id, p2.id]
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(Product.objects.count(), 1)
        self.assertFalse(Product.objects.filter(id=p1.id).exists())
        self.assertFalse(Product.objects.filter(id=p2.id).exists())
        self.assertTrue(Product.objects.filter(id=p3.id).exists())

    def test_bulk_delete_products_as_branch_admin_is_blocked(self):
        """Verifies that a Branch Admin is blocked from bulk deleting products."""
        branch_admin = InventoryUser.objects.create(
            username="branchadmin", is_active=True, role="branch_admin"
        )
        branch_admin.set_password("testpass")
        
        session = self.client.session
        session["inv_user_id"] = branch_admin.id
        session.save()
        
        p1 = Product.objects.create(name="Product 1", sku="P001", category=self.category)
        
        url = reverse("bulk-delete-products")
        data = {
            "product_ids": [p1.id]
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(id=p1.id).exists())

    def test_bulk_upload_auto_creates_categories_case_insensitively(self):
        """Verifies that bulk upload resolves categories case-insensitively and auto-creates missing ones."""
        import io
        import pandas as pd
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        self.assertEqual(Category.objects.count(), 1)
        
        df = pd.DataFrame([
            {"Name": "Bulk Product A", "Category": "new category", "SKU": "BPA001", "Serial Number": "SN-BPA-1"},
            {"Name": "Bulk Product B", "Category": "test category", "SKU": "BPB002", "Serial Number": "SN-BPB-2"}
        ])
        
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        excel_file = SimpleUploadedFile(
            name="bulk_products.xlsx",
            content=excel_buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        url = reverse("add-product")
        data = {
            "form_type": "bulk",
            "excel_file": excel_file
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(Category.objects.count(), 2)
        self.assertTrue(Category.objects.filter(name="new category").exists())
        self.assertTrue(Category.objects.filter(name="Test Category").exists())
        
        prod_a = Product.objects.get(sku="BPA001")
        prod_b = Product.objects.get(sku="BPB002")
        
        self.assertEqual(prod_a.category.name, "new category")
        self.assertEqual(prod_b.category, self.category)

    def test_online_bulk_product_creation(self):
        """Verifies that online formset creates multiple products and BranchStock records correctly."""
        from inventory.models import Branch, BranchStock
        branch = Branch.objects.create(code="TEST", name="Test Branch")
        
        url = reverse("add-product")
        data = {
            "form_type": "online_bulk",
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            
            "form-0-name": "Formset Product 1",
            "form-0-category": self.category.id,
            "form-0-branch": branch.id,
            "form-0-brand": "Brand 1",
            "form-0-model_number": "MN1",
            "form-0-sku": "FS-001",
            "form-0-serial_number": "SN-FS-1",
            "form-0-unit": "Pcs",
            "form-0-status": "in_stock",
            "form-0-supplier": "Supplier A",
            "form-0-initial_quantity": "15",
            "form-0-rack_number": "R1",
            "form-0-shelf_number": "S2",
            "form-0-local_sku": "L-FS-001",
            
            "form-1-name": "Formset Product 2",
            "form-1-category": self.category.id,
            "form-1-branch": branch.id,
            "form-1-initial_quantity": "5",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirects to products list on success
        
        self.assertEqual(Product.objects.count(), 2)
        prod1 = Product.objects.get(sku="FS-001")
        prod2 = Product.objects.get(name="Formset Product 2")
        
        self.assertEqual(prod1.brand, "Brand 1")
        self.assertEqual(prod1.category, self.category)
        
        # Verify BranchStock is created
        bs1 = BranchStock.objects.get(product=prod1, branch=branch)
        self.assertEqual(bs1.current_quantity, 15)
        self.assertEqual(bs1.rack_number, "R1")
        self.assertEqual(bs1.shelf_number, "S2")
        self.assertEqual(bs1.local_sku, "L-FS-001")
        
        bs2 = BranchStock.objects.get(product=prod2, branch=branch)
        self.assertEqual(bs2.current_quantity, 5)
        self.assertEqual(bs2.rack_number, "-")  # Defaults

    def test_online_bulk_product_validation(self):
        """Verifies that validation errors are caught and shown to the user without saving records."""
        url = reverse("add-product")
        data = {
            "form_type": "online_bulk",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            
            # Missing category (which is a required field in BulkProductForm)
            "form-0-name": "Invalid Formset Product",
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200) # Renders form page again on error
        self.assertEqual(Product.objects.count(), 0) # No products created
        self.assertIn("active_tab", response.context)
        self.assertEqual(response.context["active_tab"], "online_bulk")
