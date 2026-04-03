from rest_framework import serializers
from .models import POI, POIVote
from apps.accounts.serializers import PublicUserSerializer


class POISerializer(serializers.ModelSerializer):
    user      = PublicUserSerializer(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model  = POI
        fields = ("id", "user", "latitude", "longitude", "poi_type",
                  "description", "image", "status", "upvotes", "downvotes",
                  "user_vote", "reject_reason", "created_at", "updated_at")
        read_only_fields = ("id", "user", "status", "upvotes", "downvotes",
                            "user_vote", "reject_reason", "created_at", "updated_at")

    def get_user_vote(self, obj):
        req = self.context.get("request")
        if req and req.user.is_authenticated:
            v = POIVote.objects.filter(poi=obj, user=req.user).first()
            return v.vote_type if v else None
        return None

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)