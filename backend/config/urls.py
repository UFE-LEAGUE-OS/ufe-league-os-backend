"""
URL configuration for the League OS backend API.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.views import api_landing_view, landing_page_view


def health_check_view(request):
    return JsonResponse(
        {
            "status": "OK",
            "service": "League OS Backend API",
            "version": "sprint-1-foundation",
        }
    )


urlpatterns = [
    path("", landing_page_view, name="landing-page"),
    path("admin/", admin.site.urls),
    path("api/", api_landing_view, name="api-landing"),
    path("api/health/", health_check_view, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/accounts/", include("accounts.urls")),
    path("api/dashboards/", include("dashboards.urls")),
    path("api/governance/", include("governance.urls")),
    path("api/sponsorships/", include("sponsorships.urls")),
    path("api/ticketing/", include("ticketing.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
