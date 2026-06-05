from rest_framework import serializers
from .models import Category, Product

"""
This module defines serializers to convert model instances to/from JSON representations.
"""


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer matching Category model attributes.
    """
    class Meta:
        model = Category
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer matching Product model attributes.
    """
    class Meta:
        model = Product
        fields = "__all__"
