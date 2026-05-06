from rest_framework import serializers
from .models import Segment
from apps.accounts.serializers import PublicUserSerializer


class SegmentSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model  = Segment
        fields = ("id", "start_lat", "start_lng", "end_lat", "end_lng",
                  "geometry", "condition", "infra_level", "is_created",
                  "user", "created_at", "updated_at")
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)