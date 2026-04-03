from rest_framework import serializers
from .models import CrowdAggregation


class CrowdAggregationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CrowdAggregation
        fields = ("id", "segment_hash", "start_lat", "start_lng",
                  "end_lat", "end_lng", "green_votes", "yellow_votes",
                  "red_votes", "dominant", "updated_at")