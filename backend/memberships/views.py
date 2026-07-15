from datetime import timedelta
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import Club, User
from sponsorships.flutterwave import FlutterwaveError

from .models import (
    MembershipCard,
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)
from .serializers import (
    MembershipCardSerializer,
    MembershipPaymentSerializer,
    MembershipPlanSerializer,
    MembershipSubscriptionSerializer,
)
from .services.flutterwave_gateway import (
    initialize_membership_flutterwave_payment,
    make_membership_payment_reference,
    verify_and_confirm_membership_payment,
)
from .services.presentation_demo import (
    demo_membership_checkout_is_enabled,
    ensure_presentation_demo_membership_plan,
)


def _get_active_subscription_for_user(user):
    return (
        MembershipSubscription.objects.filter(
            user=user, status=MembershipSubscription.Status.ACTIVE
        )
        .select_related("plan", "club")
        .order_by("-created_at")
        .first()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def membership_plans_view(request):
    if request.method == "GET":
        club_id = request.query_params.get("club")
        queryset = MembershipPlan.objects.select_related("club").filter(
            is_active=True, is_visible=True
        )

        if club_id:
            queryset = queryset.filter(club_id=club_id)

        return Response(
            {
                "count": queryset.count(),
                "results": MembershipPlanSerializer(
                    queryset, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to create membership plans."},
            status=status.HTTP_403_FORBIDDEN,
        )

    club_id = request.data.get("club")
    club = Club.objects.filter(id=club_id).first() if club_id else None

    if club is None:
        return Response(
            {"detail": "Club is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = MembershipPlanSerializer(data=request.data)
    if serializer.is_valid():
        plan = serializer.save()
        return Response(
            {
                "message": "Membership plan created successfully.",
                "plan": MembershipPlanSerializer(
                    plan, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def membership_plan_detail_view(request, plan_id):
    plan = MembershipPlan.objects.select_related("club").filter(id=plan_id).first()

    if plan is None:
        return Response(
            {"detail": "Membership plan not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            MembershipPlanSerializer(plan, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    if request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to update this plan."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = MembershipPlanSerializer(plan, data=request.data, partial=True)
    if serializer.is_valid():
        plan = serializer.save()
        return Response(
            {
                "message": "Membership plan updated successfully.",
                "plan": MembershipPlanSerializer(
                    plan, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def membership_subscriptions_view(request):
    if request.method == "GET":
        subscriptions = MembershipSubscription.objects.select_related(
            "user", "plan", "club", "membership_card"
        )

        if request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
            subscriptions = subscriptions.filter(user=request.user)

        club_id = request.query_params.get("club")
        if club_id:
            subscriptions = subscriptions.filter(club_id=club_id)

        return Response(
            {
                "count": subscriptions.count(),
                "results": MembershipSubscriptionSerializer(
                    subscriptions, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    plan_id = request.data.get("plan")
    plan = MembershipPlan.objects.filter(id=plan_id, is_active=True).first()

    if plan is None:
        return Response(
            {"detail": "Selected membership plan is not available."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing = MembershipSubscription.objects.filter(
        user=request.user, plan=plan, status=MembershipSubscription.Status.ACTIVE
    ).first()

    if existing:
        return Response(
            {"detail": "You already have an active subscription for this plan."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subscription = MembershipSubscription.objects.create(
        user=request.user,
        plan=plan,
        club=plan.club,
        status=MembershipSubscription.Status.PENDING_PAYMENT,
    )

    return Response(
        {
            "message": "Membership subscription created. Proceed to payment.",
            "subscription": MembershipSubscriptionSerializer(
                subscription, context={"request": request}
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def my_membership_view(request):
    subscription = _get_active_subscription_for_user(request.user)

    if subscription is None:
        return Response(
            {"detail": "No active membership subscription found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        data = MembershipSubscriptionSerializer(
            subscription, context={"request": request}
        ).data

        card = getattr(subscription, "membership_card", None)
        data["card"] = (
            MembershipCardSerializer(card, context={"request": request}).data
            if card
            else None
        )

        return Response(data, status=status.HTTP_200_OK)

    serializer = MembershipSubscriptionSerializer(
        subscription, data=request.data, partial=True
    )

    if serializer.is_valid():
        subscription = serializer.save()
        return Response(
            MembershipSubscriptionSerializer(
                subscription, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def membership_card_view(request):
    subscription_id = request.data.get("subscription") or request.query_params.get(
        "subscription"
    )

    if subscription_id:
        subscription = (
            MembershipSubscription.objects.filter(
                id=subscription_id,
                user=request.user,
                status=MembershipSubscription.Status.ACTIVE,
            )
            .select_related("plan", "club")
            .first()
        )
    else:
        subscription = _get_active_subscription_for_user(request.user)

    if subscription is None:
        return Response(
            {"detail": "No active membership subscription found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    card, _ = MembershipCard.objects.get_or_create(
        subscription=subscription,
        defaults={
            "user": request.user,
            "club": subscription.club,
            "tier": subscription.plan.tier,
            "billing_cycle": subscription.plan.billing_cycle,
            "card_number": f"MEM-{subscription.club.slug.upper()}-{uuid4().hex[:8].upper()}",
            "qr_code_data": f"membership:{subscription.id}:{request.user.id}",
            "valid_from": timezone.now(),
            "valid_until": timezone.now() + timedelta(days=30),
        },
    )

    return Response(
        MembershipCardSerializer(card, context={"request": request}).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def membership_payments_view(request):
    subscription_id = request.query_params.get("subscription")
    queryset = MembershipPayment.objects.select_related(
        "subscription",
        "subscription__user",
        "subscription__plan",
        "subscription__club",
        "subscription_plan",
    )

    if subscription_id:
        queryset = queryset.filter(subscription_id=subscription_id)
    elif request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        queryset = queryset.filter(subscription__user=request.user)

    if request.method == "GET":
        return Response(
            {
                "count": queryset.count(),
                "results": MembershipPaymentSerializer(
                    queryset, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to record membership payments."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = MembershipPaymentSerializer(data=request.data)
    if serializer.is_valid():
        payment = serializer.save()
        return Response(
            {
                "message": "Membership payment recorded successfully.",
                "payment": MembershipPaymentSerializer(
                    payment, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def membership_initiate_payment_view(request):
    subscription_id = request.data.get("subscription")
    plan_id = request.data.get("plan")
    demo_plan_code = request.data.get("demo_plan_code") or request.data.get("tier_id")

    subscription = None

    if subscription_id:
        subscription = (
            MembershipSubscription.objects.select_related(
                "plan",
                "club",
                "user",
            )
            .filter(id=subscription_id, user=request.user)
            .first()
        )

    if subscription is None and plan_id:
        plan = (
            MembershipPlan.objects.select_related("club")
            .filter(
                id=plan_id,
                is_active=True,
                is_visible=True,
            )
            .first()
        )

        if plan is None:
            return Response(
                {"detail": "Selected membership plan is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, _ = MembershipSubscription.objects.get_or_create(
            user=request.user,
            plan=plan,
            status=MembershipSubscription.Status.PENDING_PAYMENT,
            defaults={"club": plan.club},
        )

    if (
        subscription is None
        and demo_plan_code
        and demo_membership_checkout_is_enabled()
    ):
        plan = ensure_presentation_demo_membership_plan(demo_plan_code)
        subscription, _ = MembershipSubscription.objects.get_or_create(
            user=request.user,
            plan=plan,
            status=MembershipSubscription.Status.PENDING_PAYMENT,
            defaults={"club": plan.club},
        )

    if subscription is None:
        return Response(
            {"detail": "Membership subscription or plan is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing_active = MembershipSubscription.objects.filter(
        user=request.user,
        plan=subscription.plan,
        status=MembershipSubscription.Status.ACTIVE,
    ).first()

    if existing_active:
        return Response(
            {"detail": "You already have an active subscription for this plan."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = MembershipPayment.objects.create(
        subscription=subscription,
        subscription_plan=subscription.plan,
        amount_paid=subscription.plan.price_amount,
        currency=subscription.plan.currency,
        payment_method=MembershipPayment.PaymentMethod.FLUTTERWAVE,
        provider=MembershipPayment.PaymentProvider.FLUTTERWAVE,
        transaction_reference=make_membership_payment_reference(subscription),
        status=MembershipPayment.Status.PENDING,
    )

    try:
        flutterwave_response = initialize_membership_flutterwave_payment(
            payment,
            request=request,
        )
    except FlutterwaveError as exc:
        payment.status = MembershipPayment.Status.FAILED
        payment.provider_status = "checkout_initialization_failed"
        payment.provider_response = {"error": str(exc)}
        payment.save(
            update_fields=[
                "status",
                "provider_status",
                "provider_response",
                "updated_at",
            ]
        )
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    payment.checkout_url = flutterwave_response.get("data", {}).get("link", "")
    payment.provider_status = flutterwave_response.get(
        "status",
        "checkout_initialized",
    )
    payment.provider_response = flutterwave_response
    payment.save(
        update_fields=[
            "checkout_url",
            "provider_status",
            "provider_response",
            "updated_at",
        ]
    )

    return Response(
        {
            "message": "Flutterwave membership checkout initialized successfully.",
            "payment": MembershipPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            "subscription": MembershipSubscriptionSerializer(
                subscription,
                context={"request": request},
            ).data,
            "tx_ref": payment.transaction_reference,
            "checkout_url": payment.checkout_url,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def membership_flutterwave_verify_view(request):
    tx_ref = request.query_params.get("tx_ref") or request.query_params.get("reference")

    if not tx_ref:
        return Response(
            {"detail": "tx_ref is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
                "message": "Flutterwave membership payment verification failed.",
                "detail": error_message,
                "payment": MembershipPaymentSerializer(
                    payment,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "message": "Flutterwave membership payment verified successfully.",
            "payment": MembershipPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            "subscription": MembershipSubscriptionSerializer(
                payment.subscription,
                context={"request": request},
            ).data,
            "card": (
                MembershipCardSerializer(
                    payment.subscription.membership_card,
                    context={"request": request},
                ).data
                if hasattr(payment.subscription, "membership_card")
                else None
            ),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@csrf_exempt
def membership_payment_webhook_view(request):
    transaction_reference = (
        request.data.get("transaction_reference")
        or request.data.get("tx_ref")
        or request.data.get("reference")
    )
    status_value = request.data.get("status")
    provider_status = request.data.get("provider_status", "")
    provider_response = request.data.get("provider_response", {})

    if not transaction_reference:
        return Response(
            {"detail": "transaction_reference is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = MembershipPayment.objects.filter(
        transaction_reference=transaction_reference
    ).first()

    if payment is None:
        return Response(
            {"detail": "Payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    payment.provider_status = provider_status or status_value
    payment.provider_response = provider_response

    if status_value in {"CONFIRMED", "SUCCESSFUL", "SUCCESS"}:
        payment.status = MembershipPayment.Status.CONFIRMED
        payment.paid_at = timezone.now()
        payment.provider_transaction_id = request.data.get(
            "provider_transaction_id", ""
        )

        subscription = payment.subscription
        subscription.status = MembershipSubscription.Status.ACTIVE
        subscription.starts_at = timezone.now()
        subscription.ends_at = timezone.now() + timedelta(days=30)
        subscription.save(
            update_fields=["status", "starts_at", "ends_at", "updated_at"]
        )
    elif status_value in {"FAILED", "FAILURE", "FAIL"}:
        payment.status = MembershipPayment.Status.FAILED
    elif status_value in {"CANCELLED", "CANCELED"}:
        payment.status = MembershipPayment.Status.CANCELLED

    payment.save(
        update_fields=[
            "status",
            "provider_status",
            "provider_response",
            "paid_at",
            "updated_at",
        ]
    )

    return Response({"status": "received"}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Club Admin - Members directory
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def club_members_directory_view(request):
    """
    Filterable members directory for a club.
    Supports:
      - club (required unless user is super admin)
      - status (ACTIVE, EXPIRED, PENDING_PAYMENT, CANCELLED)
      - tier (BASIC, SILVER, GOLD, PLATINUM)
      - search (email/name substring)
    """
    user = request.user

    if user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to view the members directory."},
            status=status.HTTP_403_FORBIDDEN,
        )

    club_id = request.query_params.get("club")
    status_value = request.query_params.get("status")
    tier_value = request.query_params.get("tier")
    search = (request.query_params.get("search") or "").strip().lower()

    if not club_id and user.role != User.Role.SUPER_ADMIN:
        return Response(
            {"detail": "club query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = (
        MembershipSubscription.objects.select_related(
            "user",
            "plan",
            "club",
            "membership_card",
        )
        .filter(club_id=club_id)
        .order_by("-created_at")
    )

    if status_value:
        queryset = queryset.filter(status=status_value)

    if tier_value:
        queryset = queryset.filter(plan__tier=tier_value)

    if search:
        queryset = queryset.filter(
            models.Q(user__email__icontains=search)
            | models.Q(user__first_name__icontains=search)
            | models.Q(user__last_name__icontains=search)
        )

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 20))
    start = (page - 1) * page_size
    end = start + page_size

    results = MembershipSubscriptionSerializer(
        queryset[start:end], many=True, context={"request": request}
    ).data

    return Response(
        {
            "count": queryset.count(),
            "page": page,
            "page_size": page_size,
            "results": results,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Club Admin - Membership requests approve/reject
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def membership_requests_view(request):
    """
    List membership requests (GET) or approve/reject a request (POST).
    A request is a MembershipSubscription with PENDING_PAYMENT or PENDING_APPROVAL.
    """
    user = request.user

    if user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to manage membership requests."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        club_id = request.query_params.get("club")
        if not club_id and user.role != User.Role.SUPER_ADMIN:
            return Response(
                {"detail": "club query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = MembershipSubscription.objects.select_related(
            "user",
            "plan",
            "club",
        ).filter(status=MembershipSubscription.Status.PENDING_PAYMENT)

        if club_id:
            queryset = queryset.filter(club_id=club_id)

        queryset = queryset.order_by("-created_at")

        return Response(
            {
                "count": queryset.count(),
                "results": MembershipSubscriptionSerializer(
                    queryset, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    # POST approve/reject
    subscription_id = request.data.get("subscription_id")
    action = request.data.get("action")  # "approve" or "reject"
    _reason = request.data.get("reason", "")

    if not subscription_id or action not in {"approve", "reject"}:
        return Response(
            {"detail": "subscription_id and action ('approve'|'reject') are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subscription = (
        MembershipSubscription.objects.select_related(
            "user",
            "plan",
            "club",
        )
        .filter(id=subscription_id)
        .first()
    )

    if subscription is None:
        return Response(
            {"detail": "Membership request not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if subscription.club_id and user.role != User.Role.SUPER_ADMIN:
        # Optional: restrict to the club the admin belongs to.
        pass

    if action == "approve":
        subscription.status = MembershipSubscription.Status.ACTIVE
        subscription.starts_at = timezone.now()
        subscription.ends_at = timezone.now() + timedelta(days=30)
        subscription.save(
            update_fields=["status", "starts_at", "ends_at", "updated_at"]
        )
        action_label = "approved"
    else:
        subscription.status = MembershipSubscription.Status.CANCELLED
        subscription.save(update_fields=["status", "updated_at"])
        action_label = "rejected"

    return Response(
        {
            "message": f"Membership request {action_label} successfully.",
            "subscription": MembershipSubscriptionSerializer(
                subscription, context={"request": request}
            ).data,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Membership categories & pricing CRUD (enhanced)
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def membership_categories_view(request):
    """
    List or create membership categories/plans for the admin's club.
    """
    user = request.user

    if user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to manage membership categories."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        club_id = request.query_params.get("club")
        queryset = MembershipPlan.objects.select_related("club").filter(is_active=True)

        if club_id:
            queryset = queryset.filter(club_id=club_id)

        return Response(
            {
                "count": queryset.count(),
                "results": MembershipPlanSerializer(
                    queryset, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    club_id = request.data.get("club")
    club = Club.objects.filter(id=club_id).first() if club_id else None

    if club is None:
        return Response(
            {"detail": "Club is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = MembershipPlanSerializer(data=request.data)
    if serializer.is_valid():
        plan = serializer.save()
        return Response(
            {
                "message": "Membership category created successfully.",
                "plan": MembershipPlanSerializer(
                    plan, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def membership_category_detail_view(request, plan_id):
    """
    Retrieve, update, or delete a membership category/plan.
    """
    user = request.user

    if user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to manage membership categories."},
            status=status.HTTP_403_FORBIDDEN,
        )

    plan = MembershipPlan.objects.select_related("club").filter(id=plan_id).first()

    if plan is None:
        return Response(
            {"detail": "Membership category not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            MembershipPlanSerializer(plan, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    if request.method == "PATCH":
        serializer = MembershipPlanSerializer(plan, data=request.data, partial=True)
        if serializer.is_valid():
            plan = serializer.save()
            return Response(
                {
                    "message": "Membership category updated successfully.",
                    "plan": MembershipPlanSerializer(
                        plan, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    plan.delete()
    return Response(
        {"message": "Membership category deleted successfully."},
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Membership reports & exports
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def membership_reports_export_view(request):
    """
    Export membership report for a club in CSV or PDF format.
    Query params:
      - club (required unless super admin)
      - format (csv|pdf), default csv
      - status (optional filter)
      - tier (optional filter)
    """
    user = request.user

    if user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to export membership reports."},
            status=status.HTTP_403_FORBIDDEN,
        )

    club_id = request.query_params.get("club")
    report_format = (request.query_params.get("format") or "csv").lower()
    status_value = request.query_params.get("status")
    tier_value = request.query_params.get("tier")

    if not club_id and user.role != User.Role.SUPER_ADMIN:
        return Response(
            {"detail": "club query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = MembershipSubscription.objects.select_related(
        "user",
        "plan",
        "club",
    )

    if club_id:
        queryset = queryset.filter(club_id=club_id)

    if status_value:
        queryset = queryset.filter(status=status_value)

    if tier_value:
        queryset = queryset.filter(plan__tier=tier_value)

    rows = []
    for subscription in queryset:
        rows.append(
            {
                "user_email": subscription.user.email,
                "plan_name": subscription.plan.name,
                "tier": subscription.plan.tier,
                "billing_cycle": subscription.plan.billing_cycle,
                "price": str(subscription.plan.price_amount),
                "currency": subscription.plan.currency,
                "status": subscription.status,
                "starts_at": subscription.starts_at,
                "ends_at": subscription.ends_at,
                "created_at": subscription.created_at,
            }
        )

    if report_format == "csv":
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "user_email",
                "plan_name",
                "tier",
                "billing_cycle",
                "price",
                "currency",
                "status",
                "starts_at",
                "ends_at",
                "created_at",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

        buffer.seek(0)
        response = Response(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=membership-report.csv"
        return response

    # PDF stub: return structured JSON summary for now
    return Response(
        {
            "format": "pdf",
            "message": "PDF export is not implemented yet.",
            "preview": {
                "count": len(rows),
                "columns": [
                    "user_email",
                    "plan_name",
                    "tier",
                    "billing_cycle",
                    "price",
                    "currency",
                    "status",
                    "starts_at",
                    "ends_at",
                    "created_at",
                ],
                "rows": rows[:50],
            },
        },
        status=status.HTTP_200_OK,
    )
