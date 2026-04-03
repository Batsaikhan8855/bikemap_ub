from django.contrib import admin
from .models import Segment


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display  = ("id", "condition", "infra_level", "is_created",
                     "start_lat", "start_lng", "user", "created_at")
    list_filter   = ("condition", "infra_level", "is_created")
    list_editable = ("condition",)
    search_fields = ("user__email",)