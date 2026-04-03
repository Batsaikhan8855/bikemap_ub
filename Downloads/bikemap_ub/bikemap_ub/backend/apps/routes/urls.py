from django.urls import path
from .views import GPXExportView, SmartRouteView, UpdateProfileDistanceView

urlpatterns = [
    path("gpx-export/",       GPXExportView.as_view(),          name="route-gpx-export"),
    path("smart/",            SmartRouteView.as_view(),          name="route-smart"),
    path("record-distance/",  UpdateProfileDistanceView.as_view(), name="route-record-distance"),
]