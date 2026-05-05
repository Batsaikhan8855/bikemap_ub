from django.urls import path
from .dashboard_views import (
    DashboardStatsView, PendingPOIsView,
    UserListView, UserBanView, ExportDataView, AuditLogView,
)

urlpatterns = [
    path("stats/",             DashboardStatsView.as_view(), name="dash-stats"),
    path("pending-pois/",      PendingPOIsView.as_view(),    name="dash-pending-pois"),
    path("users/",             UserListView.as_view(),        name="dash-users"),
    path("users/<int:pk>/ban/",UserBanView.as_view(),         name="dash-user-ban"),
    path("export/",            ExportDataView.as_view(),      name="dash-export"),
    path("audit-log/",         AuditLogView.as_view(),        name="dash-audit-log"),
]