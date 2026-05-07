from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum

from apps.segments.models import Segment
from apps.pois.models import POI
from .models import CrowdAggregation
from .serializers import CrowdAggregationSerializer


class AggregationListView(generics.ListAPIView):
    """
    GET /api/aggregation/       — all aggregated segments (public)
    GET /api/aggregation/?dominant=green — filter by dominant condition
    Used by frontend map to colour-code segments — US-031
    """
    serializer_class   = CrowdAggregationSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields   = ["dominant"]

    def get_queryset(self):
        return CrowdAggregation.objects.exclude(dominant="none")


class HeatmapDataView(APIView):
    """
    GET /api/aggregation/heatmap/
    Lightweight list for heatmap overlay — E5, E6
    Returns lat/lng + dominant colour for every aggregated cell
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = CrowdAggregation.objects.exclude(dominant="none").values(
            "start_lat", "start_lng", "end_lat", "end_lng",
            "dominant", "green_votes", "yellow_votes", "red_votes"
        )
        return Response(list(data))


class PublicStatsView(APIView):
    """
    GET /api/aggregation/stats/
    Системийн ерөнхий статистик — нийтэд нээлттэй (зочин ч харж болно).
    Зорилго: /stats/ хуудас дээр харуулж BikeMap UB системийн өсөлт,
    хамрах хүрээ, нийт оролцоог нэг газарт нэгтгэж харуулах.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        User = get_user_model()

        # ─── Сегмент: нийт + condition + infra_level задаргаа ──────
        seg_total = Segment.objects.count()
        seg_by_cond = dict(
            Segment.objects.values_list("condition")
            .annotate(n=Count("id"))
            .values_list("condition", "n")
        )
        seg_by_lvl = dict(
            Segment.objects.values_list("infra_level")
            .annotate(n=Count("id"))
            .values_list("infra_level", "n")
        )
        seg_manual   = Segment.objects.filter(is_created=True).count()
        seg_imported = seg_total - seg_manual

        # ─── POI: нийт + төрөл + статус ────────────────────────────
        poi_total = POI.objects.count()
        poi_by_type = dict(
            POI.objects.values_list("poi_type")
            .annotate(n=Count("id"))
            .values_list("poi_type", "n")
        )
        poi_by_status = dict(
            POI.objects.values_list("status")
            .annotate(n=Count("id"))
            .values_list("status", "n")
        )

        # ─── Хэрэглэгчид + нийт явсан км ───────────────────────────
        user_total = User.objects.count()
        # total_distance_km field маш олон хэрэглэгчтэй User model-д бий
        total_km = (User.objects
                    .aggregate(s=Sum("total_distance_km"))
                    .get("s") or 0)

        # ─── Bike-lane coverage % (rough estimate) ─────────────────
        # green = "bike lane present" гэсэн утгатай
        green = seg_by_cond.get("green", 0)
        coverage_pct = (green * 100.0 / seg_total) if seg_total else 0

        # ─── Aggregation хүснэгт (Crowd Aggregation хэдэн cell-д ажилласан) ──
        agg_total = CrowdAggregation.objects.exclude(dominant="none").count()

        return Response({
            "segments": {
                "total":    seg_total,
                "by_condition":  seg_by_cond,    # {green: N, yellow: N, red: N}
                "by_infra_level": seg_by_lvl,    # {1: N, 2: N, ..., 6: N}
                "manual":   seg_manual,
                "imported": seg_imported,
            },
            "pois": {
                "total":     poi_total,
                "by_type":   poi_by_type,
                "by_status": poi_by_status,
            },
            "users": {
                "total":          user_total,
                "total_km":       float(total_km),
            },
            "coverage": {
                "green_pct":      round(coverage_pct, 1),
                "aggregations":   agg_total,
            },
        })