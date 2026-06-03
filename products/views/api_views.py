from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from ..models import Category, Product
from ..serializers import CategorySerializer, ProductSerializer
from inventory.utils import get_isolated_products


class CategoryListCreate(ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class ProductListCreate(ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_isolated_products(self.request.user)
