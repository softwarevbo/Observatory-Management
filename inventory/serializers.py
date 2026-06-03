from rest_framework import serializers

from products.serializers import ProductSerializer

from .models import Alert, InventoryAdjustment, QuantityLimit, SerialNumber


class InventoryAdjustmentSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = InventoryAdjustment
        fields = [
            "id",
            "product",
            "product_id",
            "adjustment_type",
            "quantity",
            "reason",
            "timestamp",
            "created_by",
        ]


class SerialNumberSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = SerialNumber
        fields = [
            "id",
            "serial_number",
            "product",
            "product_id",
            "status",
            "created_at",
        ]


class QuantityLimitSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = QuantityLimit
        fields = [
            "id",
            "product",
            "product_id",
            "limit_quantity",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
        ]


class AlertSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    acknowledged_by = serializers.ReadOnlyField(source="acknowledged_by.username")
    resolved_by = serializers.ReadOnlyField(source="resolved_by.username")

    class Meta:
        model = Alert
        fields = [
            "id",
            "product",
            "product_id",
            "alert_type",
            "status",
            "message",
            "current_quantity",
            "limit_quantity",
            "created_at",
            "acknowledged_at",
            "resolved_at",
            "acknowledged_by",
            "resolved_by",
        ]
