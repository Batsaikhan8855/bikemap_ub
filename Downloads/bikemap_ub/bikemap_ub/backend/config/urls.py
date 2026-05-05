from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── OpenAPI / Swagger documentation ──────────────────────────────────────
    path('api/schema/',          SpectacularAPIView.as_view(),         name='schema'),
    path('api/docs/',            SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',           SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # ── Frontend pages ───────────────────────────────────────────────────────
    path('', TemplateView.as_view(template_name='map/index.html'), name='home'),
    path('map/', TemplateView.as_view(template_name='map/index.html'), name='map'),
    path('heatmap/', TemplateView.as_view(template_name='map/heatmap.html'), name='heatmap'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard/index.html'), name='dashboard'),
    path('login/', TemplateView.as_view(template_name='auth/login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='auth/register.html'), name='register'),
    path('profile/', TemplateView.as_view(template_name='auth/profile.html'), name='profile'),

    # ── REST API ─────────────────────────────────────────────────────────────
    path('api/auth/',         include('apps.accounts.urls')),
    path('api/segments/',     include('apps.segments.urls')),
    path('api/pois/',         include('apps.pois.urls')),
    path('api/aggregation/',  include('apps.aggregation.urls')),
    path('api/routes/',       include('apps.routes.urls')),
    path('api/dashboard/',    include('apps.accounts.dashboard_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
