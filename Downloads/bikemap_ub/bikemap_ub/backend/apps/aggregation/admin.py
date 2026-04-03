from django.contrib import admin
from .models import CrowdAggregation


@admin.register(CrowdAggregation)
class CrowdAggregationAdmin(admin.ModelAdmin):
    list_display  = ("segment_hash", "dominant", "green_votes",
                     "yellow_votes", "red_votes", "updated_at")
    list_filter   = ("dominant",)
    search_fields = ("segment_hash",)
    readonly_fields = ("segment_hash", "dominant", "updated_at")