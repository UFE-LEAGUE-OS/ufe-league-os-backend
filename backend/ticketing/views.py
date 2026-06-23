from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from dashboards.models import Match
from sponsorships.flutterwave import FlutterwaveError

from .models import Ticket, TicketOrder, TicketType, TicketValidationLog
from .serializers import (
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
    mark_ticket_order_payment_failed,
    validate_ticket_code,
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


@api_view(["GET"])
@permission_classes([AllowAny])
def match_ticket_types_view(request, match_id):
    match = Match.objects.filter(id=match_id).first()

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_tickets_view(request):
    tickets = (
        Ticket.objects.filter(owner=request.user)
        .select_related("order", "ticket_type", "match")
        .order_by("-issued_at")
    )

    return Response(
        {
            "count": tickets.count(),
            "tickets": serialize_tickets(tickets, request),
        },
        status=status.HTTP_200_OK,
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
