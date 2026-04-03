from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SegmentViewSet

router = DefaultRouter()
router.register(r"", SegmentViewSet, basename="segment")
urlpatterns = [path("", include(router.urls))]