from rest_framework import serializers

from .models import StockEntry


class StockEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = StockEntry
        fields = "__all__"
        read_only_fields = ["timestamp", "created_by"]
