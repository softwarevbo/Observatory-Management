from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from inventory.models import BranchStock
from inventory.utils import filter_by_branch
from ..models import StockEntry
from ..serializers import StockEntrySerializer


class StockIn(ListCreateAPIView):
    serializer_class = StockEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(
            StockEntry.objects.filter(entry_type="in"), self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, entry_type="in")


class StockOut(ListCreateAPIView):
    serializer_class = StockEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_branch(
            StockEntry.objects.filter(entry_type="out"), self.request.user
        )

    def perform_create(self, serializer):
        product, quantity = (
            serializer.validated_data["product"],
            serializer.validated_data["quantity"],
        )
        user_branch = getattr(self.request.user, "branch", None)
        source_stock = BranchStock.objects.filter(
            product=product, branch=user_branch
        ).first()
        available_quantity = source_stock.current_quantity if source_stock else 0
        if quantity > available_quantity:
            raise ValidationError(
                f"Cannot remove {quantity} units. Only {available_quantity} available in this branch."
            )
        serializer.save(
            created_by=self.request.user, entry_type="out", branch=user_branch
        )
