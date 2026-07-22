from io import BytesIO
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import qrcode
import qrcode.image.svg

from accounts.models import User
from dashboards.models import (
    LeagueAdminScope,
    Match,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from sponsorships.flutterwave import FlutterwaveError

from decimal import Decimal
from .models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketType,
    TicketValidationLog,
)
from .serializers import (
    ExpireTicketReservationsSerializer,
    FlutterwaveTicketCheckoutSerializer,
    TicketOrderSerializer,
    TicketSalesMonitoringSerializer,
    TicketSerializer,
    TicketTypeAdminSerializer,
    TicketTypeInventoryUpdateSerializer,
    TicketTypePublishSerializer,
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


def ticket_validation_matches_for_user(user):
    """
    Return only matches the authenticated user may validate.

    The ticketing dashboard already scopes visible matches, but
    this server-side check prevents users from manually posting
    an unrelated match ID to the validation endpoint.
    """
    if user.is_staff or user.role == User.Role.SUPER_ADMIN:
        return Match.objects.all()

    scope_filters = []

    if user.role in {
        User.Role.CLUB_ADMIN,
        User.Role.TICKETING_OFFICER,
    }:
        club_ids = set()

        if user.club_id:
            club_ids.add(user.club_id)

        club_ids.update(
            user.administered_clubs.values_list(
                "id",
                flat=True,
            )
        )

        if club_ids:
            scope_filters.append(
                Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids)
            )

    if user.role == User.Role.LEAGUE_ADMIN:
        scopes = list(
            LeagueAdminScope.objects.filter(
                user=user,
                is_active=True,
            ).values_list(
                "league_id",
                "competition_id",
            )
        )

        full_league_ids = {
            league_id for league_id, competition_id in scopes if competition_id is None
        }

        competition_ids = {
            competition_id for _, competition_id in scopes if competition_id is not None
        }

        if full_league_ids:
            scope_filters.append(Q(competition__league_id__in=(full_league_ids)))

        if competition_ids:
            scope_filters.append(Q(competition_id__in=competition_ids))

    if user.role in {
        User.Role.UNION_ADMIN,
        User.Role.TICKETING_OFFICER,
    }:
        memberships = UnionWorkspaceMembership.objects.filter(
            user=user,
            is_active=True,
            workspace__status=(UnionWorkspace.Status.ACTIVE),
            workspace__related_union__isnull=False,
        ).select_related("workspace")

        union_ids = set()

        for membership in memberships:
            may_scan = False

            if user.role == User.Role.UNION_ADMIN:
                may_scan = membership.role in {
                    UnionWorkspaceMembership.Role.OWNER,
                    UnionWorkspaceMembership.Role.UNION_ADMIN,
                }

            if user.role == User.Role.TICKETING_OFFICER:
                permissions = set(membership.effective_permissions)

                may_scan = bool(
                    {
                        "union.ticketing.manage",
                        "union.ticketing.scan",
                    }.intersection(permissions)
                )

            if may_scan:
                union_ids.add(membership.workspace.related_union_id)

        if union_ids:
            scope_filters.append(Q(competition__league__union_id__in=(union_ids)))

    if not scope_filters:
        return Match.objects.none()

    combined_filter = scope_filters[0]

    for scope_filter in scope_filters[1:]:
        combined_filter |= scope_filter

    return Match.objects.filter(combined_filter).distinct()


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
    match_id = serializer.validated_data["match_id"]

    allowed_match = (
        ticket_validation_matches_for_user(request.user).filter(id=match_id).first()
    )

    if allowed_match is None:
        return Response(
            {
                "detail": (
                    "You are not authorised to validate " "tickets for this match."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    ticket, log = validate_ticket_code(
        scanned_code=scanned_code,
        scanned_by=request.user,
        match_id=allowed_match.id,
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


def user_can_manage_ticket_types(user):
    """Check if user can manage ticket types (club admin, league admin, super admin, ticketing officer)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.role in {
        User.Role.CLUB_ADMIN,
        User.Role.LEAGUE_ADMIN,
        User.Role.UNION_ADMIN,
        User.Role.SUPER_ADMIN,
        User.Role.TICKETING_OFFICER,
    }


def get_managed_matches_for_user(user):
    """Return queryset of matches the user can manage ticket types for."""
    if user.is_staff or user.role == User.Role.SUPER_ADMIN:
        return Match.objects.all()

    scope_filters = []

    if user.role in {User.Role.CLUB_ADMIN, User.Role.TICKETING_OFFICER}:
        club_ids = set()
        if user.club_id:
            club_ids.add(user.club_id)
        club_ids.update(user.administered_clubs.values_list("id", flat=True))
        if club_ids:
            scope_filters.append(
                Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids)
            )
        # Ticketing officers may be scoped to a union via workspace
        if user.role == User.Role.TICKETING_OFFICER:
            memberships = UnionWorkspaceMembership.objects.filter(
                user=user,
                is_active=True,
                workspace__status=UnionWorkspace.Status.ACTIVE,
                workspace__related_union__isnull=False,
            ).select_related("workspace")
            union_ids = set()
            for membership in memberships:
                permissions = set(membership.effective_permissions)
                if {"union.ticketing.manage", "union.ticketing.scan"}.intersection(
                    permissions
                ):
                    union_ids.add(membership.workspace.related_union_id)
            if union_ids:
                scope_filters.append(Q(competition__league__union_id__in=union_ids))

    if user.role == User.Role.LEAGUE_ADMIN:
        scopes = LeagueAdminScope.objects.filter(user=user, is_active=True).values_list(
            "league_id", "competition_id"
        )
        full_league_ids = {lid for lid, cid in scopes if cid is None}
        competition_ids = {cid for _, cid in scopes if cid is not None}
        if full_league_ids:
            scope_filters.append(Q(competition__league_id__in=full_league_ids))
        if competition_ids:
            scope_filters.append(Q(competition_id__in=competition_ids))

    if user.role == User.Role.UNION_ADMIN:
        memberships = UnionWorkspaceMembership.objects.filter(
            user=user,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            workspace__related_union__isnull=False,
        ).select_related("workspace")
        union_ids = set()
        for membership in memberships:
            if membership.role in {
                UnionWorkspaceMembership.Role.OWNER,
                UnionWorkspaceMembership.Role.UNION_ADMIN,
            }:
                union_ids.add(membership.workspace.related_union_id)
        if union_ids:
            scope_filters.append(Q(competition__league__union_id__in=union_ids))

    if not scope_filters:
        return Match.objects.none()

    q = scope_filters[0]
    for f in scope_filters[1:]:
        q |= f
    return Match.objects.filter(q).distinct()


# ---- Ticket Type Management (Admin) ----


@extend_schema(
    tags=["Ticketing Admin"],
    summary="List ticket types for managed matches",
    description="Returns ticket types for matches the authenticated user can manage.",
    responses={200: TicketTypeAdminSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_ticket_types_list_view(request):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    managed_matches = get_managed_matches_for_user(request.user)
    ticket_types = TicketType.objects.select_related(
        "match", "match__home_club", "match__away_club", "created_by"
    ).filter(match__in=managed_matches)

    # Filters
    match_id = request.query_params.get("match_id")
    status_param = request.query_params.get("status")
    if match_id:
        ticket_types = ticket_types.filter(match_id=match_id)
    if status_param:
        ticket_types = ticket_types.filter(status=status_param)

    ticket_types = ticket_types.order_by("match", "price", "name")

    return Response(
        {
            "count": ticket_types.count(),
            "results": TicketTypeAdminSerializer(
                ticket_types, many=True, context={"request": request}
            ).data,
        },
        status=200,
    )


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Create a ticket type",
    description="Create a new ticket type for a managed match.",
    request=TicketTypeSerializer,
    responses={201: TicketTypeSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_create_view(request):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    serializer = TicketTypeSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    match = serializer.validated_data.get("match")

    # Ensure user can manage this match
    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=match.id).exists():
        return Response(
            {"detail": "You cannot create ticket types for this match."}, status=403
        )

    serializer.save(created_by=request.user)
    return Response(serializer.data, status=201)


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Retrieve a ticket type",
    responses={200: TicketTypeAdminSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_detail_view(request, pk):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    ticket_type = (
        TicketType.objects.select_related(
            "match", "match__home_club", "match__away_club", "created_by"
        )
        .filter(pk=pk)
        .first()
    )
    if ticket_type is None:
        return Response({"detail": "Ticket type not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=ticket_type.match_id).exists():
        return Response({"detail": "You cannot view this ticket type."}, status=403)

    return Response(
        TicketTypeAdminSerializer(ticket_type, context={"request": request}).data,
        status=200,
    )


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Update a ticket type",
    request=TicketTypeSerializer,
    responses={200: TicketTypeSerializer},
)
@api_view(["PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_update_view(request, pk):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    ticket_type = TicketType.objects.select_related("match").filter(pk=pk).first()
    if ticket_type is None:
        return Response({"detail": "Ticket type not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=ticket_type.match_id).exists():
        return Response({"detail": "You cannot update this ticket type."}, status=403)

    partial = request.method == "PATCH"
    serializer = TicketTypeSerializer(
        ticket_type, data=request.data, partial=partial, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=200)


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Delete a ticket type",
    responses={204: None},
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_delete_view(request, pk):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    ticket_type = TicketType.objects.select_related("match").filter(pk=pk).first()
    if ticket_type is None:
        return Response({"detail": "Ticket type not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=ticket_type.match_id).exists():
        return Response({"detail": "You cannot delete this ticket type."}, status=403)

    # Prevent deletion if orders exist
    if TicketOrderItem.objects.filter(ticket_type=ticket_type).exists():
        return Response(
            {"detail": "Cannot delete ticket type with existing orders."}, status=400
        )

    ticket_type.delete()
    return Response(status=204)


# ---- Inventory Management ----


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Update ticket type inventory",
    request=TicketTypeInventoryUpdateSerializer,
    responses={200: TicketTypeAdminSerializer},
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_inventory_view(request, pk):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket inventory."},
            status=403,
        )

    ticket_type = TicketType.objects.select_related("match").filter(pk=pk).first()
    if ticket_type is None:
        return Response({"detail": "Ticket type not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=ticket_type.match_id).exists():
        return Response(
            {"detail": "You cannot update this ticket type inventory."}, status=403
        )

    serializer = TicketTypeInventoryUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    new_quantity = serializer.validated_data["quantity_available"]

    if new_quantity < ticket_type.quantity_sold:
        return Response(
            {
                "detail": f"Cannot set inventory below already sold quantity ({ticket_type.quantity_sold})."
            },
            status=400,
        )

    ticket_type.quantity_available = new_quantity
    ticket_type.save(update_fields=["quantity_available", "updated_at"])

    return Response(
        TicketTypeAdminSerializer(ticket_type, context={"request": request}).data,
        status=200,
    )


# ---- Publish / Status Management ----


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Publish, unpublish, sell out, or reopen ticket types",
    request=TicketTypePublishSerializer,
    responses={200: TicketTypeAdminSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_ticket_type_publish_view(request, pk):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    ticket_type = TicketType.objects.select_related("match").filter(pk=pk).first()
    if ticket_type is None:
        return Response({"detail": "Ticket type not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=ticket_type.match_id).exists():
        return Response({"detail": "You cannot update this ticket type."}, status=403)

    serializer = TicketTypePublishSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    action = serializer.validated_data["action"]
    sale_start_at = serializer.validated_data.get("sale_start_at")
    sale_end_at = serializer.validated_data.get("sale_end_at")

    if action == "publish":
        ticket_type.status = TicketType.Status.ACTIVE
        if (
            ticket_type.quantity_available is None
            or ticket_type.quantity_available == 0
        ):
            return Response(
                {
                    "detail": "Cannot publish ticket type with zero inventory. Set quantity_available first."
                },
                status=400,
            )
    elif action == "unpublish":
        ticket_type.status = TicketType.Status.DRAFT
    elif action == "sell_out":
        ticket_type.status = TicketType.Status.SOLD_OUT
    elif action == "reopen":
        ticket_type.status = TicketType.Status.ACTIVE

    if sale_start_at is not None:
        ticket_type.sale_start_at = sale_start_at
    if sale_end_at is not None:
        ticket_type.sale_end_at = sale_end_at

    ticket_type.save(
        update_fields=["status", "sale_start_at", "sale_end_at", "updated_at"]
    )

    return Response(
        TicketTypeAdminSerializer(ticket_type, context={"request": request}).data,
        status=200,
    )


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Publish sale for all ticket types of a match",
    description="Set all ACTIVE ticket types for a match to a publish status with optional window.",
    request=serializers.Serializer,
    responses={
        200: {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "updated_count": {"type": "integer"},
            },
        }
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_match_publish_sale_view(request, match_id):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to manage ticket types."}, status=403
        )

    match = Match.objects.filter(id=match_id).first()
    if match is None:
        return Response({"detail": "Match not found."}, status=404)

    managed_matches = get_managed_matches_for_user(request.user)
    if not managed_matches.filter(id=match.id).exists():
        return Response(
            {"detail": "You cannot manage ticket sales for this match."}, status=403
        )

    sale_start_at = request.data.get("sale_start_at")
    sale_end_at = request.data.get("sale_end_at")

    qs = TicketType.objects.filter(match=match, status=TicketType.Status.DRAFT)
    if sale_start_at is not None:
        qs = qs.exclude(
            sale_start_at__isnull=False
        )  # preserve existing if provided? We'll allow override below explicitly
    # Override for all target statuses
    if sale_start_at is not None:
        qs = TicketType.objects.filter(
            match=match, status__in=[TicketType.Status.DRAFT, TicketType.Status.ACTIVE]
        )
    updated = 0
    for tt in qs:
        tt.status = TicketType.Status.ACTIVE
        if sale_start_at is not None:
            tt.sale_start_at = sale_start_at
        if sale_end_at is not None:
            tt.sale_end_at = sale_end_at
        if tt.quantity_available is None or tt.quantity_available == 0:
            continue  # skip zero inventory types
        tt.save(update_fields=["status", "sale_start_at", "sale_end_at", "updated_at"])
        updated += 1

    return Response(
        {"message": "Match sale publish attempted.", "updated_count": updated},
        status=200,
    )


# ---- Monitoring / Performance ----


@extend_schema(
    tags=["Ticketing Admin"],
    summary="Ticket sales monitoring",
    description="Aggregate performance metrics across managed matches.",
    responses={200: TicketSalesMonitoringSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_sales_monitoring_view(request):
    if not user_can_manage_ticket_types(request.user):
        return Response(
            {"detail": "You do not have permission to view ticket sales."}, status=403
        )

    managed_matches = get_managed_matches_for_user(request.user)
    ticket_types = TicketType.objects.select_related(
        "match",
        "match__competition",
        "match__home_club",
        "match__away_club",
        "created_by",
    ).filter(match__in=managed_matches)

    # Filters
    match_id = request.query_params.get("match_id")
    status_param = request.query_params.get("status")
    if match_id:
        ticket_types = ticket_types.filter(match_id=match_id)
    if status_param:
        ticket_types = ticket_types.filter(status=status_param)

    matches_data = {}
    for tt in ticket_types:
        mid = tt.match_id
        if mid not in matches_data:
            matches_data[mid] = {
                "match": tt.match,
                "ticket_types": [],
                "total_quantity_available": 0,
                "total_quantity_sold": 0,
                "total_revenue": Decimal("0"),
                "total_orders": 0,
                "sold_out_types": 0,
                "active_types": 0,
            }
        entry = matches_data[mid]
        entry["ticket_types"].append(tt)
        entry["total_quantity_available"] += tt.quantity_available
        entry["total_quantity_sold"] += tt.quantity_sold
        entry["total_revenue"] += tt.revenue_generated
        entry["total_orders"] += tt.tickets_sold_count
        if tt.status == TicketType.Status.SOLD_OUT:
            entry["sold_out_types"] += 1
        if tt.status == TicketType.Status.ACTIVE:
            entry["active_types"] += 1

    matches_stats = []
    for mid, entry in matches_data.items():
        m = entry["match"]
        matches_stats.append(
            {
                "match_id": m.id,
                "match_label": str(m),
                "match_date": m.match_date,
                "venue": m.venue,
                "status": m.status,
                "ticket_types_count": len(entry["ticket_types"]),
                "total_quantity_available": entry["total_quantity_available"],
                "total_quantity_sold": entry["total_quantity_sold"],
                "total_revenue": entry["total_revenue"],
                "total_orders": entry["total_orders"],
                "sold_out_types": entry["sold_out_types"],
                "active_types": entry["active_types"],
            }
        )

    matches_stats.sort(key=lambda x: x["match_date"], reverse=True)

    overview = {
        "managed_matches_count": len(matches_stats),
        "total_ticket_types": ticket_types.count(),
        "total_quantity_available": sum(
            e["total_quantity_available"] for e in matches_stats
        ),
        "total_quantity_sold": sum(e["total_quantity_sold"] for e in matches_stats),
        "total_revenue": sum(e["total_revenue"] for e in matches_stats),
        "total_orders": sum(e["total_orders"] for e in matches_stats),
        "sold_out_types": sum(e["sold_out_types"] for e in matches_stats),
        "active_types": sum(e["active_types"] for e in matches_stats),
    }

    return Response(
        {
            "overview": overview,
            "matches": matches_stats,
            "ticket_types": TicketTypeAdminSerializer(
                ticket_types.order_by("-updated_at"),
                many=True,
                context={"request": request},
            ).data,
        },
        status=200,
    )
