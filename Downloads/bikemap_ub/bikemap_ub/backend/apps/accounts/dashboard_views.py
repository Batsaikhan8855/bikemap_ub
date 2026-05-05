from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, permissions
from django.http import HttpResponse
from .models import User
from .serializers import UserProfileSerializer
from .permissions import IsModeratorOrAdmin, IsAdminOnly
from apps.pois.models import POI
from apps.segments.models import Segment
from apps.audit_log.models import AuditLog
import csv, datetime


class DashboardStatsView(APIView):
    """GET /api/dashboard/stats/  — E6 US-050"""
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request):
        from apps.pois.models import POI
        from apps.segments.models import Segment

        poi_by_type = {}
        for poi_type, _ in POI.POI_TYPE_CHOICES:
            poi_by_type[poi_type] = POI.objects.filter(poi_type=poi_type, status="approved").count()

        total_segs  = Segment.objects.count()
        green_segs  = Segment.objects.filter(condition="green").count()
        coverage    = round(green_segs / total_segs * 100, 1) if total_segs else 0

        # Top 5 danger areas by POI density
        from django.db.models import Count
        top5 = (POI.objects
                .filter(status="approved", poi_type__in=["danger","road_damage"])
                .values("poi_type")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")[:5])

        return Response({
            "total_segments":     total_segs,
            "total_pois":         POI.objects.count(),
            "pending_pois":       POI.objects.filter(status="pending").count(),
            "total_users":        User.objects.count(),
            "bike_lane_coverage": coverage,
            "pois_by_type":       poi_by_type,
            "top5_danger_areas":  list(top5),
        })


class PendingPOIsView(APIView):
    """GET /api/dashboard/pending-pois/  — E6 US-051"""
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request):
        from apps.pois.serializers import POISerializer
        pois = POI.objects.filter(status="pending").select_related("user")
        return Response(POISerializer(pois, many=True).data)


class UserListView(generics.ListAPIView):
    """GET /api/dashboard/users/  — E6 US-052"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAdminOnly]
    queryset           = User.objects.all().order_by("-created_at")


class UserBanView(APIView):
    """POST /api/dashboard/users/{pk}/ban/  — E6 US-052"""
    permission_classes = [IsAdminOnly]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        user.is_banned = not user.is_banned
        user.save()
        action = "user_ban" if user.is_banned else "user_unban"
        AuditLog.log(actor=request.user, action=action,
                     target_type="User", target_id=user.id, request=request)
        return Response({"is_banned": user.is_banned, "username": user.username})


class ExportDataView(APIView):
    """GET /api/dashboard/export/?type=pois|segments  — E6 US-053"""
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request):
        export_type = request.query_params.get("type", "pois")
        date_from   = request.query_params.get("from")
        date_to     = request.query_params.get("to")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f"attachment; filename=bikemap_{export_type}_{datetime.date.today()}.csv"
        )
        writer = csv.writer(response)

        if export_type == "pois":
            qs = POI.objects.all()
            if date_from: qs = qs.filter(created_at__date__gte=date_from)
            if date_to:   qs = qs.filter(created_at__date__lte=date_to)
            writer.writerow(["id","poi_type","latitude","longitude",
                              "status","upvotes","downvotes","created_at"])
            for p in qs:
                writer.writerow([p.id, p.poi_type, p.latitude, p.longitude,
                                  p.status, p.upvotes, p.downvotes, p.created_at])
        else:
            qs = Segment.objects.all()
            if date_from: qs = qs.filter(created_at__date__gte=date_from)
            if date_to:   qs = qs.filter(created_at__date__lte=date_to)
            writer.writerow(["id","start_lat","start_lng","end_lat","end_lng",
                              "condition","infra_level","created_at"])
            for s in qs:
                writer.writerow([s.id, s.start_lat, s.start_lng,
                                  s.end_lat, s.end_lng, s.condition,
                                  s.infra_level, s.created_at])
        return response


class AuditLogView(generics.ListAPIView):
    """GET /api/dashboard/audit-log/  — Audit trail (admin only)"""
    permission_classes = [IsAdminOnly]

    def get(self, request):
        from apps.audit_log.models import AuditLog as AL
        qs = AL.objects.select_related("actor").order_by("-created_at")[:200]
        data = [
            {
                "id":          e.id,
                "actor":       e.actor.username if e.actor else "system",
                "action":      e.action,
                "target_type": e.target_type,
                "target_id":   e.target_id,
                "detail":      e.detail,
                "ip_address":  e.ip_address,
                "created_at":  e.created_at,
            }
            for e in qs
        ]
        return Response(data)