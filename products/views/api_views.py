from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from ..models import Category, Product
from ..serializers import CategorySerializer, ProductSerializer
from inventory.utils import get_isolated_products

"""
This module processes REST API endpoints for categories and products.
"""


class CategoryListCreate(ListCreateAPIView):
    """
    API endpoint to list or create product categories programmatically.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class ProductListCreate(ListCreateAPIView):
    """
    API endpoint to list or create products programmatically.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Enforce branch isolation rules on API results
        return get_isolated_products(self.request.user)
