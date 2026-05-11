from django.urls import path
from .views import (
    GPXExportView, GPXImportView, GPXImportSaveView, SmartRouteView,
    UpdateProfileDistanceView, SnapToRoadView, GPXClassifyView,
)

urlpatterns = [
    path("gpx-export/",       GPXExportView.as_view(),             name="route-gpx-export"),
    path("gpx-import/",       GPXImportView.as_view(),             name="route-gpx-import"),
    path("gpx-import/save/",  GPXImportSaveView.as_view(),         name="route-gpx-import-save"),
    path("gpx-classify/",     GPXClassifyView.as_view(),           name="route-gpx-classify"),
    path("smart/",            SmartRouteView.as_view(),             name="route-smart"),
    path("record-distance/",  UpdateProfileDistanceView.as_view(), name="route-record-distance"),
    path("snap/",             SnapToRoadView.as_view(),             name="route-snap"),
]