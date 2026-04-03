from django.contrib import admin
from .models import POI, POIVote


@admin.register(POI)
class POIAdmin(admin.ModelAdmin):
    list_display  = ("id","poi_type","latitude","longitude","status",
                     "upvotes","downvotes","user","created_at")
    list_filter   = ("poi_type","status")
    list_editable = ("status",)
    search_fields = ("description","user__email")
    actions       = ["approve_selected"]

    @admin.action(description="Approve selected POIs")
    def approve_selected(self, request, queryset):
        queryset.update(status="approved")


@admin.register(POIVote)
class POIVoteAdmin(admin.ModelAdmin):
    list_display = ("poi","user","vote_type","created_at")
    list_filter  = ("vote_type",)