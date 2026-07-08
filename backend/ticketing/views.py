from io import BytesIO
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import qrcode
import qrcode.image.svg

from accounts.models import User
from dashboards.models import Match
from sponsorships.flutterwave import FlutterwaveError

from .models import Ticket, TicketOrder, TicketType, TicketValidationLog
from .serializers import (
    ExpireTicketReservationsSerializer,
    FlutterwaveTicketCheckoutSerializer,
    TicketOrderSerializer,
    TicketSerializer,
    TicketTypeSerializer,
    TicketValidationResultSerializer,
    TicketValidationSerializer,
)
from .services.flutterwave_gateway import (
    extract_flutterwave_tx_ref,
    flutterwave_webhook_signature_is_valid,
    get_ticket_order_by_reference,
    initialize_ticket_flutterwave_payment,
    validate_ticket_flutterwave_transaction,
    verify_flutterwave_transaction,
)
from .services.orders import (
    confirm_ticket_order_payment,
    create_ticket_order,
    expire_stale_ticket_reservations,
    mark_ticket_order_payment_failed,
    validate_ticket_code,
)
from .services.presentation_demo import (
    demo_checkout_is_enabled,
    ensure_presentation_demo_ticketing_match,
)

TICKET_VALIDATION_ROLES = {
    User.Role.TICKETING_OFFICER,
    User.Role.CLUB_ADMIN,
    User.Role.LEAGUE_ADMIN,
    User.Role.UNION_ADMIN,
    User.Role.SUPER_ADMIN,
}


def user_can_validate_tickets(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.role in TICKET_VALIDATION_ROLES)
    )


def serialize_order(order, request):
    return TicketOrderSerializer(order, context={"request": request}).data


def serialize_tickets(tickets, request):
    return TicketSerializer(tickets, many=True, context={"request": request}).data


@extend_schema(
    tags=["Ticketing"],
    summary="List ticket types for a match",
    description=(
        "Returns active ticket types for a match, including available stock, "
        "reserved stock, and remaining quantity."
    ),
    responses={200: OpenApiResponse(response=TicketTypeSerializer)},
    examples=[
        OpenApiExample(
            "Ticket type listing response",
            value={
                "match": {
                    "id": 1,
                    "label": "KOBS Rugby Club vs Heathens Rugby Club",
                    "venue": "Legends Rugby Grounds",
                    "match_date": "2026-07-10T16:00:00Z",
                    "status": "SCHEDULED",
                },
                "count": 1,
                "ticket_types": [
                    {
                        "id": 1,
                        "match": 1,
                        "match_label": "KOBS Rugby Club vs Heathens Rugby Club",
                        "name": "Ordinary",
                        "description": "Ordinary match access ticket.",
                        "price": "10000.00",
                        "currency": "UGX",
                        "quantity_available": 100,
                        "quantity_sold": 0,
                        "active_reserved_quantity": 2,
                        "remaining_quantity": 98,
                        "status": "ACTIVE",
                    }
                ],
            },
            response_only=True,
        )
    ],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def match_ticket_types_view(request, match_id):
    match = Match.objects.filter(id=match_id).first()

    if match is None and demo_checkout_is_enabled():
        match = ensure_presentation_demo_ticketing_match(match_id)

    if match is None:
        return Response(
            {"detail": "Match not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    ticket_types = TicketType.objects.select_related(
        "match",
        "match__home_club",
        "match__away_club",
    ).filter(match=match)

    include_inactive = request.query_params.get("include_inactive") == "true"
    if not include_inactive:
        ticket_types = ticket_types.filter(status=TicketType.Status.ACTIVE)

    if not ticket_types.exists() and demo_checkout_is_enabled():
        match = ensure_presentation_demo_ticketing_match(match_id)
        ticket_types = TicketType.objects.select_related(
            "match",
            "match__home_club",
            "match__away_club",
        ).filter(match=match)
        if not include_inactive:
            ticket_types = ticket_types.filter(status=TicketType.Status.ACTIVE)

    return Response(
        {
            "match": {
                "id": match.id,
                "label": str(match),
                "venue": match.venue,
                "match_date": match.match_date,
                "status": match.status,
            },
            "count": ticket_types.count(),
            "ticket_types": TicketTypeSerializer(
                ticket_types,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="List authenticated fan ticket orders",
    description="Returns only the ticket orders owned by the authenticated user.",
    responses={200: TicketOrderSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_ticket_orders_view(request):
    orders = (
        TicketOrder.objects.filter(buyer=request.user)
        .prefetch_related("items", "items__ticket_type", "tickets")
        .order_by("-created_at")
    )

    return Response(
        {
            "count": orders.count(),
            "orders": TicketOrderSerializer(
                orders,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="Initialize Flutterwave ticket checkout",
    description=(
        "Creates a pending ticket order, reserves ticket stock for the configured "
        "reservation window, initializes Flutterwave checkout, and returns the "
        "hosted checkout URL."
    ),
    request=FlutterwaveTicketCheckoutSerializer,
    responses={201: TicketOrderSerializer},
    examples=[
        OpenApiExample(
            "Checkout request",
            value={"ticket_type_id": 1, "quantity": 2},
            request_only=True,
        ),
        OpenApiExample(
            "Checkout response",
            value={
                "message": "Flutterwave ticket checkout initialized successfully.",
                "order": {
                    "id": 12,
                    "total_amount": "20000.00",
                    "currency": "UGX",
                    "status": "PENDING",
                    "provider": "FLUTTERWAVE",
                    "reservation_expires_at": "2026-07-10T14:10:00Z",
                    "is_reservation_active": True,
                },
                "tx_ref": "LOS-TICKET-1-abc123",
                "checkout_url": "https://checkout.flutterwave.com/...",
            },
            response_only=True,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ticket_order_flutterwave_initialize_view(request):
    serializer = FlutterwaveTicketCheckoutSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    ticket_type = serializer.validated_data["ticket_type"]
    quantity = serializer.validated_data["quantity"]

    order = create_ticket_order(
        buyer=request.user,
        ticket_type=ticket_type,
        quantity=quantity,
    )

    try:
        flutterwave_response = initialize_ticket_flutterwave_payment(
            order,
            request=request,
        )
    except FlutterwaveError as exc:
        mark_ticket_order_payment_failed(
            order,
            provider_response={"error": str(exc)},
            provider_status="checkout_initialization_failed",
        )
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    checkout_url = flutterwave_response.get("data", {}).get("link", "")

    order.checkout_url = checkout_url
    order.checkout_initialized_at = timezone.now()
    order.provider_status = flutterwave_response.get("status", "checkout_initialized")
    order.provider_response = flutterwave_response
    order.save(
        update_fields=[
            "checkout_url",
            "checkout_initialized_at",
            "provider_status",
            "provider_response",
            "updated_at",
        ]
    )

    return Response(
        {
            "message": "Flutterwave ticket checkout initialized successfully.",
            "order": serialize_order(order, request),
            "tx_ref": order.payment_reference,
            "checkout_url": checkout_url,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="List authenticated fan tickets",
    description="Returns only issued tickets owned by the authenticated user.",
    responses={200: TicketSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_tickets_view(request):
    tickets = (
        Ticket.objects.filter(owner=request.user)
        .select_related(
            "order",
            "ticket_type",
            "match",
            "match__competition",
            "match__home_club",
            "match__away_club",
        )
        .order_by("-issued_at")
    )

    return Response(
        {
            "count": tickets.count(),
            "tickets": serialize_tickets(tickets, request),
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="Verify Flutterwave ticket payment",
    description=(
        "Verifies the Flutterwave transaction using tx_ref, marks the order as "
        "paid, releases the reservation, and issues tickets."
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ticket_flutterwave_verify_view(request):
    tx_ref = request.query_params.get("tx_ref") or request.query_params.get("reference")

    if not tx_ref:
        return Response(
            {"detail": "tx_ref is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    order = get_ticket_order_by_reference(tx_ref)

    if order is None:
        return Response(
            {"detail": "Ticket order not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        flutterwave_response = verify_flutterwave_transaction(tx_ref)
    except FlutterwaveError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    is_valid, error_message = validate_ticket_flutterwave_transaction(
        order,
        flutterwave_response,
    )

    if not is_valid:
        status_value = flutterwave_response.get("data", {}).get("status", "failed")
        order = mark_ticket_order_payment_failed(
            order,
            provider_response=flutterwave_response,
            provider_status=status_value,
        )
        return Response(
            {
                "message": "Flutterwave ticket payment verification failed.",
                "detail": error_message,
                "order": serialize_order(order, request),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    order, tickets = confirm_ticket_order_payment(
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
            "message": "Flutterwave ticket payment verified successfully.",
            "order": serialize_order(order, request),
            "tickets": serialize_tickets(tickets, request),
        },
        status=status.HTTP_200_OK,
    )


@csrf_exempt
@extend_schema(
    tags=["Ticketing"],
    summary="Flutterwave ticket payment webhook",
    description=(
        "Accepts Flutterwave webhook callbacks, verifies the transaction, "
        "and confirms the matching ticket order if valid."
    ),
)
@api_view(["POST"])
@permission_classes([AllowAny])
def ticket_flutterwave_webhook_view(request):
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

    order = get_ticket_order_by_reference(tx_ref)
    if order is None:
        return Response(
            {"detail": "Ticket order not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        flutterwave_response = verify_flutterwave_transaction(tx_ref)
    except FlutterwaveError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

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
        {"message": "Webhook received and ticket payment confirmed."},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="Validate/check in a ticket",
    request=TicketValidationSerializer,
    responses={200: TicketValidationResultSerializer},
    examples=[
        OpenApiExample(
            "Validate ticket request",
            value={
                "scanned_code": "5b3b26c4-f4c8-4971-b233-927c27eeb11f",
                "match_id": 1,
            },
            request_only=True,
        )
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ticket_validate_view(request):
    if not user_can_validate_tickets(request.user):
        return Response(
            {"detail": "You do not have permission to validate tickets."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = TicketValidationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    scanned_code = serializer.validated_data["scanned_code"]
    match_id = serializer.validated_data.get("match_id")

    ticket, log = validate_ticket_code(
        scanned_code=scanned_code,
        scanned_by=request.user,
        match_id=match_id,
    )

    response_status = status.HTTP_200_OK
    if log.result != TicketValidationLog.Result.VALID:
        response_status = status.HTTP_400_BAD_REQUEST

    response_data = TicketValidationResultSerializer(
        log,
        context={"request": request},
    ).data

    if ticket is not None:
        response_data["ticket"] = TicketSerializer(
            ticket,
            context={"request": request},
        ).data

    return Response(response_data, status=response_status)


@extend_schema(
    tags=["Ticketing"],
    summary="Expire stale ticket reservations",
    description=(
        "Admin/QA helper endpoint. Expires unpaid pending ticket reservations "
        "whose reservation window has already passed."
    ),
    request=ExpireTicketReservationsSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def expire_ticket_reservations_view(request):
    if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
        return Response(
            {"detail": "Only staff or super admins can expire ticket reservations."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ExpireTicketReservationsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    dry_run = serializer.validated_data.get("dry_run", False)

    expired_queryset = TicketOrder.objects.filter(
        status=TicketOrder.Status.PENDING,
        reservation_released_at__isnull=True,
        reservation_expires_at__isnull=False,
        reservation_expires_at__lte=timezone.now(),
    )

    expired_count = expired_queryset.count()

    if not dry_run:
        expired_count = expire_stale_ticket_reservations()

    return Response(
        {
            "message": "Ticket reservation expiry check completed.",
            "dry_run": dry_run,
            "expired_count": expired_count,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Ticketing"],
    summary="Get ticket QR code as SVG",
    description=(
        "Returns a real scannable SVG QR code for an authenticated ticket owner. "
        "The QR payload can be scanned and submitted to the ticket validation endpoint."
    ),
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ticket_qr_svg_view(request, ticket_id):
    ticket = Ticket.objects.filter(id=ticket_id, owner=request.user).first()

    if ticket is None:
        return Response(
            {"detail": "Ticket not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    qr_image = qrcode.make(
        f"LOS-TICKET:{ticket.ticket_code}",
        image_factory=qrcode.image.svg.SvgImage,
        box_size=10,
        border=4,
    )

    buffer = BytesIO()
    qr_image.save(buffer)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="image/svg+xml",
    )
    response["Content-Disposition"] = (
        f'inline; filename="{ticket.qr_download_filename}"'
    )
    return response
