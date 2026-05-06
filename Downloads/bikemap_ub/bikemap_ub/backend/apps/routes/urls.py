from django.urls import path
from .views import (
    GPXExportView, GPXImportView, SmartRouteView,
    UpdateProfileDistanceView, SnapToRoadView,
)

urlpatterns = [
    path("gpx-export/",       GPXExportView.as_view(),            name="route-gpx-export"),
    path("gpx-import/",       GPXImportView.as_view(),            name="route-gpx-import"),
    path("smart/",            SmartRouteView.as_view(),            name="route-smart"),
    path("record-distance/",  UpdateProfileDistanceView.as_view(), name="route-record-distance"),
    path("snap/",             SnapToRoadView.as_view(),            name="route-snap"),
]