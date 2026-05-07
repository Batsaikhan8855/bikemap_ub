from django.urls import path
from .views import AggregationListView, HeatmapDataView, PublicStatsView

urlpatterns = [
    path("",         AggregationListView.as_view(), name="aggregation-list"),
    path("heatmap/", HeatmapDataView.as_view(),     name="aggregation-heatmap"),
    path("stats/",   PublicStatsView.as_view(),     name="public-stats"),
]