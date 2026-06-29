from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny

from memberships.services.flutterwave_gateway import (
    verify_and_confirm_membership_payment,
)
from sponsorships.flutterwave import FlutterwaveError
from ticketing.services.flutterwave_gateway import (
    extract_flutterwave_tx_ref,
    flutterwave_webhook_signature_is_valid,
    get_ticket_order_by_reference,
    validate_ticket_flutterwave_transaction,
    verify_flutterwave_transaction,
)
from ticketing.services.orders import (
    confirm_ticket_order_payment,
    mark_ticket_order_payment_failed,
)

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
            "ticketing": request.build_absolute_uri("/api/ticketing/"),
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
            {
                "title": "Ticketing API",
                "description": (
                    "Match ticket checkout, Flutterwave payment verification, "
                    "and QR validation."
                ),
                "url": request.build_absolute_uri("/api/ticketing/"),
                "label": "/api/ticketing/",
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


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_exempt
def global_flutterwave_webhook_view(request):
    """
    Global Flutterwave webhook endpoint.

    Flutterwave allows one test webhook URL, so this endpoint routes payment
    callbacks to the correct League OS payment flow using the tx_ref prefix.

    Supported references:
    - LOS-TICKET-...
    - LOS-MEMBERSHIP-...
    """

    if not flutterwave_webhook_signature_is_valid(request):
        return Response(
            {"detail": "Invalid Flutterwave webhook signature."},
            status=status.HTTP_403_FORBIDDEN,
        )

    tx_ref = extract_flutterwave_tx_ref(request.data)

    if not tx_ref:
        return Response(
            {"detail": "No transaction reference found in webhook payload."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if tx_ref.startswith("LOS-TICKET-"):
        order = get_ticket_order_by_reference(tx_ref)

        if order is None:
            return Response(
                {"detail": "Ticket order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            flutterwave_response = verify_flutterwave_transaction(tx_ref)
        except FlutterwaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        is_valid, error_message = validate_ticket_flutterwave_transaction(
            order,
            flutterwave_response,
        )

        if not is_valid:
            status_value = flutterwave_response.get("data", {}).get("status", "failed")
            mark_ticket_order_payment_failed(order, flutterwave_response, status_value)

            return Response(
                {
                    "message": "Webhook received, but ticket payment was not confirmed.",
                    "detail": error_message,
                    "tx_ref": tx_ref,
                },
                status=status.HTTP_200_OK,
            )

        confirm_ticket_order_payment(
            order,
            provider_response=flutterwave_response,
            provider_transaction_id=str(
                flutterwave_response.get("data", {}).get("id")
                or flutterwave_response.get("data", {}).get("flw_ref")
                or ""
            ),
            provider_status=flutterwave_response.get("data", {}).get(
                "status",
                "successful",
            ),
        )

        return Response(
            {
                "message": "Ticket payment webhook received and confirmed.",
                "tx_ref": tx_ref,
            },
            status=status.HTTP_200_OK,
        )

    if tx_ref.startswith("LOS-MEMBERSHIP-"):
        try:
            payment, error_message = verify_and_confirm_membership_payment(tx_ref)
        except FlutterwaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if payment is None:
            return Response(
                {"detail": "Membership payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if error_message:
            return Response(
                {
                    "message": "Webhook received, but membership payment was not confirmed.",
                    "detail": error_message,
                    "tx_ref": tx_ref,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "message": "Membership payment webhook received and confirmed.",
                "tx_ref": tx_ref,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "detail": "Unsupported Flutterwave transaction reference.",
            "tx_ref": tx_ref,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
