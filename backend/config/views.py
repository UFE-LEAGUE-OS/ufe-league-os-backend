from django.urls import reverse
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_landing_view(request):
    """Return a discoverable landing page for the League OS API."""

    return Response(
        {
            "name": "League OS Backend API",
            "status": "online",
            "version": "sprint-1-foundation",
            "description": (
                "Backend API for League OS fan engagement, authentication, "
                "clubs, dashboards, governance, sponsorships, ticketing, "
                "membership, and sports operations."
            ),
            "documentation": {
                "swagger": request.build_absolute_uri(reverse("swagger-ui")),
                "openapi_schema": request.build_absolute_uri(reverse("schema")),
            },
            "health": request.build_absolute_uri(reverse("health-check")),
            "resources": {
                "accounts": request.build_absolute_uri("/api/accounts/"),
                "dashboards": request.build_absolute_uri("/api/dashboards/"),
                "governance": request.build_absolute_uri("/api/governance/"),
                "sponsorships": request.build_absolute_uri("/api/sponsorships/"),
            },
            "staging_frontend": "https://ufe-league-os-frontend.onrender.com",
        }
    )
