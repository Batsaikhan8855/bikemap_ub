from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import POI, POIVote
from .serializers import POISerializer
from apps.accounts.permissions import (
    IsCyclistOrAbove, IsModeratorOrAdmin, IsOwnerOrMod
)


class POIViewSet(viewsets.ModelViewSet):
    """
    GET    /api/pois/                — list approved POIs (public)
    POST   /api/pois/                — create POI, status=pending (US-020)
    GET    /api/pois/{id}/           — detail
    PATCH  /api/pois/{id}/           — edit own POI (re-pends if approved)
    DELETE /api/pois/{id}/           — delete
    POST   /api/pois/{id}/vote/      — upvote/downvote (US-022)
    POST   /api/pois/{id}/approve/   — approve (mod/admin) (US-051)
    POST   /api/pois/{id}/reject/    — reject with reason (US-051)
    """
    serializer_class = POISerializer
    filterset_fields = ["poi_type", "status"]
    ordering_fields  = ["created_at", "upvotes"]

    def get_queryset(self):
        qs = POI.objects.all()
        # Public sees only approved; mods see all
        if not (self.request.user.is_authenticated
                and self.request.user.is_admin_or_mod):
            qs = qs.filter(status="approved")
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [IsCyclistOrAbove()]
        if self.action in ("approve", "reject"):
            return [IsModeratorOrAdmin()]
        return [IsOwnerOrMod()]

    def perform_create(self, serializer):
        poi  = serializer.save(user=self.request.user, status="pending")
        user = self.request.user
        user.total_pois += 1
        user.save(update_fields=["total_pois"])

    def perform_update(self, serializer):
        # Re-pend if an approved POI is edited by owner — US-061
        instance = self.get_object()
        new_status = instance.status
        if instance.status == "approved":
            new_status = "pending"
        serializer.save(status=new_status)

    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        """POST /api/pois/{id}/vote/  — US-022"""
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)
        poi       = self.get_object()
        vote_type = request.data.get("vote_type")
        if vote_type not in ("up", "down"):
            return Response({"error": "vote_type must be up or down"}, status=400)

        with transaction.atomic():
            existing = POIVote.objects.filter(poi=poi, user=request.user).first()
            if existing:
                if existing.vote_type == vote_type:
                    # Toggle off
                    if vote_type == "up":
                        poi.upvotes = max(0, poi.upvotes - 1)
                    else:
                        poi.downvotes = max(0, poi.downvotes - 1)
                    existing.delete()
                    poi.save()
                    return Response({"status": "vote_removed"})
                else:
                    # Switch vote
                    if vote_type == "up":
                        poi.upvotes   += 1
                        poi.downvotes  = max(0, poi.downvotes - 1)
                    else:
                        poi.downvotes += 1
                        poi.upvotes    = max(0, poi.upvotes - 1)
                    existing.vote_type = vote_type
                    existing.save()
            else:
                POIVote.objects.create(poi=poi, user=request.user, vote_type=vote_type)
                if vote_type == "up":
                    poi.upvotes += 1
                else:
                    poi.downvotes += 1
            poi.save()

        return Response({"upvotes": poi.upvotes, "downvotes": poi.downvotes,
                          "user_vote": vote_type})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """POST /api/pois/{id}/approve/  — US-051"""
        poi = self.get_object()
        poi.status = "approved"
        poi.save()
        return Response({"status": "approved", "id": poi.id})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """POST /api/pois/{id}/reject/  — US-051"""
        poi = self.get_object()
        reason = request.data.get("reason", "")
        if not reason:
            return Response({"error": "Rejection reason is required"}, status=400)
        poi.status = "rejected"
        poi.reject_reason = reason
        poi.save()
        return Response({"status": "rejected"})