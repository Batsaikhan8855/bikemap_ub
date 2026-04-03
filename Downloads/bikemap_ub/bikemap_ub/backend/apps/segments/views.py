from rest_framework import viewsets, permissions
from .models import Segment
from .serializers import SegmentSerializer
from apps.accounts.permissions import IsCyclistOrAbove, IsOwnerOrMod
from apps.aggregation.tasks import update_aggregation


class SegmentViewSet(viewsets.ModelViewSet):
    """
    GET    /api/segments/            — list all segments (public)
    POST   /api/segments/            — create segment (US-010 US-013)
    PATCH  /api/segments/{id}/       — update condition (US-010)
    DELETE /api/segments/{id}/       — delete (owner / mod)
    """
    queryset           = Segment.objects.all()
    serializer_class   = SegmentSerializer
    filterset_fields   = ["condition", "infra_level", "is_created"]
    search_fields      = []
    ordering_fields    = ["created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [IsCyclistOrAbove()]
        return [IsOwnerOrMod()]

    def perform_create(self, serializer):
        seg = serializer.save(user=self.request.user)
        # Trigger crowd aggregation update for this segment area
        update_aggregation(seg)
        # Update user stats
        user = self.request.user
        user.total_segments += 1
        user.save(update_fields=["total_segments"])

    def perform_update(self, serializer):
        seg = serializer.save()
        update_aggregation(seg)