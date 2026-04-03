from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as Base
from .models import User


@admin.register(User)
class UserAdmin(Base):
    list_display  = ("email","username","role","total_distance_km",
                     "total_pois","is_banned","created_at")
    list_filter   = ("role","is_banned")
    search_fields = ("email","username")
    list_editable = ("role","is_banned")
    fieldsets = Base.fieldsets + (
        ("BikeMap Profile", {"fields": (
            "role","bio","avatar",
            "total_distance_km","total_pois","total_segments","is_banned"
        )}),
    )