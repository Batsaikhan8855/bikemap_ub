from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import POIViewSet

router = DefaultRouter()
router.register(r"", POIViewSet, basename="poi")
urlpatterns = [path("", include(router.urls))]