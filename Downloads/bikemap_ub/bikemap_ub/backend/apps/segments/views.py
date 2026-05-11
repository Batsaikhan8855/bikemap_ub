from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Segment
from .serializers import SegmentSerializer
from apps.accounts.permissions import IsCyclistOrAbove, IsOwnerOrMod
from apps.aggregation.tasks import update_aggregation
from apps.audit_log.models import AuditLog


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

    # Map-руу бүх segment нэг удаагийн request-ээр ачаална. Default
    # PAGE_SIZE=30 нь зөвхөн 30 ширхгийг буцаадаг тул газрын зурагт
    # хангалттай дата орохгүй. (3000 segment ≈ 600 KB JSON — OK.)
    pagination_class = None

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

    def perform_destroy(self, instance):
        """Сегмент устгах + audit log + aggregation шинэчлэх"""
        seg_id = instance.id
        # aggregation-г шинэчлэхийн тулд устгахаас өмнө хадгалах
        snapshot = {
            "start_lat": instance.start_lat, "start_lng": instance.start_lng,
            "end_lat":   instance.end_lat,   "end_lng":   instance.end_lng,
        }
        AuditLog.log(
            actor=self.request.user,
            action="segment_delete",
            target_type="Segment",
            target_id=seg_id,
            detail=f"condition={instance.condition}, infra_level={instance.infra_level}",
            request=self.request,
        )
        instance.delete()
        # aggregation-ийг тухайн орон зайн нүдэнд дахин тооцоолох
        try:
            class _Snap:  # тооцоололд хэрэгтэй field-үүдтэй wrapper
                pass
            tmp = _Snap()
            for k, v in snapshot.items():
                setattr(tmp, k, v)
            update_aggregation(tmp)
        except Exception:
            pass

    @action(detail=False, methods=["post"], permission_classes=[IsCyclistOrAbove],
            url_path="bulk-import")
    def bulk_import(self, request):
        """
        POST /api/segments/bulk-import/
        Body: { "segments": [{start_lat, start_lng, end_lat, end_lng,
                               condition, infra_level}, ...] }
        Bulk-creates segments from a GPX import — max 500 per call.
        """
        segments_data = request.data.get("segments", [])
        if not segments_data:
            return Response({"error": "segments list is required"}, status=400)
        if len(segments_data) > 500:
            return Response({"error": "Maximum 500 segments per import"}, status=400)

        created_ids = []
        errors = []
        for i, seg_data in enumerate(segments_data):
            serializer = SegmentSerializer(data=seg_data,
                                           context={"request": request})
            if not serializer.is_valid():
                errors.append({"index": i, "errors": serializer.errors})
                continue
            seg = Segment.objects.create(**serializer.validated_data,
                                         user=request.user)
            update_aggregation(seg)
            created_ids.append(seg.id)

        if created_ids:
            user = request.user
            user.total_segments += len(created_ids)
            user.save(update_fields=["total_segments"])

        return Response(
            {"created": len(created_ids), "errors": errors},
            status=status.HTTP_201_CREATED,
        )