from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail, BadHeaderError
from django.urls import reverse
from rest_framework import status
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


def _is_valid_email_debug_request(request):
    configured_token = getattr(settings, "EMAIL_DEBUG_TOKEN", "")
    provided_token = request.headers.get("X-Email-Debug-Token", "")

    return bool(configured_token) and provided_token == configured_token


def _masked_email_user(value):
    if not value or "@" not in value:
        return value

    local_part, domain = value.split("@", 1)
    if len(local_part) <= 4:
        masked_local = local_part[:1] + "***"
    else:
        masked_local = local_part[:4] + "***"

    return f"{masked_local}@{domain}"


@api_view(["GET"])
def email_debug_status_view(request):
    """Temporarily expose non-secret email settings for Render debugging."""

    if not _is_valid_email_debug_request(request):
        return Response(
            {"detail": "Not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "email_backend": settings.EMAIL_BACKEND,
            "email_host": settings.EMAIL_HOST,
            "email_port": settings.EMAIL_PORT,
            "email_host_user": _masked_email_user(settings.EMAIL_HOST_USER),
            "email_use_tls": settings.EMAIL_USE_TLS,
            "email_use_ssl": settings.EMAIL_USE_SSL,
            "default_from_email": settings.DEFAULT_FROM_EMAIL,
            "server_email": settings.SERVER_EMAIL,
        }
    )


@api_view(["POST"])
def email_debug_send_view(request):
    """Temporarily send a live SMTP test email from Render."""

    if not _is_valid_email_debug_request(request):
        return Response(
            {"detail": "Not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    recipient = request.data.get("email")

    if not recipient:
        return Response(
            {"email": "This field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = send_mail(
            subject="League OS Render Brevo SMTP Probe",
            message=(
                "This is a live Render SMTP delivery test from League OS.\n\n"
                "If you received this email, Brevo SMTP is working from Render."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except (SMTPException, OSError, BadHeaderError) as exc:
        return Response(
            {
                "sent": 0,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "from_email": settings.DEFAULT_FROM_EMAIL,
                "recipient": recipient,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "sent": result,
            "recipient": recipient,
            "from_email": settings.DEFAULT_FROM_EMAIL,
        }
    )
