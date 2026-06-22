from django.shortcuts import render
from django.urls import reverse
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


def build_api_landing_payload(request):
    """Build the shared League OS API landing payload."""

    return {
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
        "quick_links": [
            {
                "title": "API Documentation",
                "description": "Explore all available endpoints in Swagger UI.",
                "url": request.build_absolute_uri(reverse("swagger-ui")),
                "label": "/api/docs/",
            },
            {
                "title": "Health Check",
                "description": "Confirm the backend service is online.",
                "url": request.build_absolute_uri(reverse("health-check")),
                "label": "/api/health/",
            },
            {
                "title": "OpenAPI Schema",
                "description": "View the generated OpenAPI schema.",
                "url": request.build_absolute_uri(reverse("schema")),
                "label": "/api/schema/",
            },
            {
                "title": "Accounts API",
                "description": "Registration, login, OTP, profile, and user flows.",
                "url": request.build_absolute_uri("/api/accounts/"),
                "label": "/api/accounts/",
            },
            {
                "title": "Dashboards API",
                "description": "Role-based fan, club, league, union, and sponsor data.",
                "url": request.build_absolute_uri("/api/dashboards/"),
                "label": "/api/dashboards/",
            },
            {
                "title": "Sponsorships API",
                "description": "Sponsor accounts, packages, agreements, and payments.",
                "url": request.build_absolute_uri("/api/sponsorships/"),
                "label": "/api/sponsorships/",
            },
        ],
        "staging_frontend": "https://ufe-league-os-frontend.onrender.com",
    }


def landing_page_view(request):
    """Render a clean public landing page at the backend root URL."""

    return render(
        request,
        "api_landing.html",
        {
            "api": build_api_landing_payload(request),
        },
    )


@api_view(["GET"])
@renderer_classes([JSONRenderer])
def api_landing_view(request):
    """Return a JSON discoverable landing page for the League OS API."""

    return Response(build_api_landing_payload(request))