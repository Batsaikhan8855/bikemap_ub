from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
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