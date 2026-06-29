"""
Extra views for the accounts app.

Provides fan-facing endpoints for:
- Follow/Unfollow clubs, leagues, unions, competitions
- Notification preferences
- Interest & privacy preferences
- Wallet & payment history
- Personalized feed aggregation
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit

from .models import NotificationPreference
from .serializers import (
    CombinedPaymentHistoryItemSerializer,
    FeedItemSerializer,
    FollowActionSerializer,
    FollowResponseSerializer,
    InterestPreferenceSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
    WalletSummarySerializer,
)
from .services import (
    aggregate_feed,
    follow_entity,
    get_combined_payment_history,
    get_or_create_interest_preferences,
    get_or_create_notification_preferences,
    mark_notification_read,
    mark_all_notifications_read,
    list_user_notifications,
    get_unread_notification_count,
    get_user_follows,
    get_wallet_payment_center,
    is_following,
    mark_all_feed_read,
    mark_feed_item_read,
    unfollow_entity,
)

# ---------------------------------------------------------------------------
# Follow / Unfollow API
# ---------------------------------------------------------------------------


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def follow_view(request):
    """
    Manage follow relationships for the authenticated user.

    GET   /api/accounts/follow/          - List all follows
    POST  /api/accounts/follow/          - Follow an entity
    DELETE /api/accounts/follow/         - Unfollow an entity
    """
    user = request.user

    if request.method == "GET":
        follows = get_user_follows(user)
        return Response(follows, status=status.HTTP_200_OK)

    serializer = FollowActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    content_type = serializer.validated_data["content_type"]
    object_id = serializer.validated_data["object_id"]

    if request.method == "POST":
        follow, created = follow_entity(user, content_type, object_id)
        if created:
            resp_serializer = FollowResponseSerializer(follow)
            return Response(resp_serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {"detail": "Already following this entity."},
            status=status.HTTP_409_CONFLICT,
        )

    # DELETE
    deleted = unfollow_entity(user, content_type, object_id)
    if deleted:
        return Response(
            {"detail": "Successfully unfollowed."},
            status=status.HTTP_200_OK,
        )
    return Response(
        {"detail": "Not currently following this entity."},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def check_follow_view(request, content_type, object_id):
    """Check if the authenticated user follows a specific entity."""
    is_following_user = is_following(request.user, content_type.upper(), object_id)
    return Response(
        {
            "is_following": is_following_user,
            "content_type": content_type.upper(),
            "object_id": object_id,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Notification Preferences API
# ---------------------------------------------------------------------------


def _update_notification_preferences(user, request_data):
    """
    Shared helper for old and new notification preference endpoints.
    """

    data = request_data

    if isinstance(data, dict) and "preferences" in data:
        data = data["preferences"]

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return None, [{"error": "Expected an object, a list, or a preferences list."}]

    updated = []
    errors = []

    for pref_data in data:
        event_type = pref_data.get("event_type")
        if not event_type:
            errors.append({"error": "event_type is required for each preference."})
            continue

        pref, _ = NotificationPreference.objects.get_or_create(
            user=user,
            event_type=event_type,
        )
        serializer = NotificationPreferenceSerializer(
            pref,
            data=pref_data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            updated.append(serializer.data)
        else:
            errors.append(serializer.errors)

    return updated, errors


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def notification_preferences_me_view(request):
    """
    Get or update the authenticated user's notification preferences.

    GET   /api/accounts/notification-preferences/me/
    PATCH /api/accounts/notification-preferences/me/
    """
    user = request.user

    if request.method == "GET":
        prefs = get_or_create_notification_preferences(user)
        serializer = NotificationPreferenceSerializer(prefs, many=True)
        return Response(
            {
                "count": len(serializer.data),
                "preferences": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    updated, errors = _update_notification_preferences(user, request.data)

    response_data = {"updated": updated or []}
    if errors:
        response_data["errors"] = errors
        return Response(response_data, status=status.HTTP_207_MULTI_STATUS)

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticatedAudit])
def notification_preferences_view(request):
    """
    Backwards-compatible notification preferences endpoint.

    GET /api/accounts/notifications/
    PUT /api/accounts/notifications/
    """
    user = request.user

    if request.method == "GET":
        prefs = get_or_create_notification_preferences(user)
        serializer = NotificationPreferenceSerializer(prefs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    updated, errors = _update_notification_preferences(user, request.data)

    response_data = {"updated": updated or []}
    if errors:
        response_data["errors"] = errors
        return Response(response_data, status=status.HTTP_207_MULTI_STATUS)

    return Response(response_data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Interest & Privacy Preferences API
# ---------------------------------------------------------------------------


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def interest_preferences_view(request):
    """
    Get or update the authenticated user's interest and privacy preferences.

    GET   /api/accounts/interests/          - Get preferences
    PATCH /api/accounts/interests/          - Update preferences
    """
    user = request.user
    pref = get_or_create_interest_preferences(user)

    if request.method == "GET":
        serializer = InterestPreferenceSerializer(pref)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = InterestPreferenceSerializer(pref, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Wallet API
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def wallet_view(request):
    """
    Get the authenticated user's MVP wallet/payment center.

    GET /api/accounts/wallet/

    Important:
    The MVP wallet does not store user money. It summarizes payment history,
    purchased tickets, memberships, and sponsorship payments.
    """
    limit = _safe_positive_int(
        request.query_params.get("limit"), default=10, maximum=50
    )
    wallet_data = get_wallet_payment_center(request.user, limit=limit)
    serializer = WalletSummarySerializer(wallet_data)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Payment History API
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def payment_history_view(request):
    """
    Get the authenticated user's combined payment history.

    GET /api/accounts/payments/

    Query params:
    - payment_type: TICKET_PURCHASE, MEMBERSHIP_FEE, SPONSORSHIP, REFUND
    - status: SUCCESSFUL, PENDING, FAILED, CANCELLED, REFUNDED
    - source: TICKETING, MEMBERSHIPS, SPONSORSHIPS, LEGACY
    - limit
    - offset
    """
    payment_type = request.query_params.get("payment_type")
    status_filter = request.query_params.get("status")
    source = request.query_params.get("source")
    limit = _safe_positive_int(
        request.query_params.get("limit"), default=50, maximum=100
    )
    offset = _safe_positive_int(request.query_params.get("offset"), default=0)

    items, total = get_combined_payment_history(
        request.user,
        payment_type=payment_type,
        status=status_filter,
        source=source,
        limit=limit,
        offset=offset,
    )

    serializer = CombinedPaymentHistoryItemSerializer(items, many=True)
    return Response(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Personalized Feed API
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def feed_view(request):
    """
    Get the authenticated user's personalized feed.

    GET /api/accounts/feed/          - Get feed
    Query params: limit, offset, item_type, unread_only
    """
    user = request.user
    limit = _safe_positive_int(
        request.query_params.get("limit"), default=50, maximum=100
    )
    offset = _safe_positive_int(request.query_params.get("offset"), default=0)
    item_type = request.query_params.get("item_type")
    unread_only = request.query_params.get("unread_only", "").lower() == "true"

    items, total = aggregate_feed(
        user,
        limit=limit,
        offset=offset,
        item_type=item_type,
        unread_only=unread_only,
    )
    serializer = FeedItemSerializer(items, many=True)
    return Response(
        {
            "count": total,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def feed_mark_read_view(request, feed_item_id):
    """Mark a single feed item as read."""
    success = mark_feed_item_read(request.user, feed_item_id)
    if success:
        return Response(
            {"detail": "Feed item marked as read."}, status=status.HTTP_200_OK
        )
    return Response(
        {"detail": "Feed item not found."},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def feed_mark_all_read_view(request):
    """Mark all feed items as read for the authenticated user."""
    count = mark_all_feed_read(request.user)
    return Response(
        {"detail": f"{count} feed items marked as read."},
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def feed_unread_count_view(request):
    """Get the count of unread feed items."""
    from .services import get_unread_feed_count

    count = get_unread_feed_count(request.user)
    return Response({"unread_count": count}, status=status.HTTP_200_OK)


def _safe_positive_int(value, default, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if number < 0:
        number = default

    if maximum is not None:
        number = min(number, maximum)

    return number


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def notification_inbox_view(request):
    """
    Get the authenticated user's in-app notification inbox.

    GET /api/accounts/notifications/inbox/

    Query params:
    - limit
    - offset
    - unread_only=true
    - category=TICKET, PAYMENT, MEMBERSHIP, FANTASY, etc.
    """
    limit = _safe_positive_int(
        request.query_params.get("limit"),
        default=50,
        maximum=100,
    )
    offset = _safe_positive_int(request.query_params.get("offset"), default=0)
    unread_only = request.query_params.get("unread_only", "").lower() == "true"
    category = request.query_params.get("category")

    items, total = list_user_notifications(
        request.user,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        category=category,
    )

    serializer = NotificationSerializer(items, many=True)

    return Response(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "unread_count": get_unread_notification_count(request.user),
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def notification_unread_count_view(request):
    """
    Get unread notification count for navbar/header badge.

    GET /api/accounts/notifications/unread-count/
    """
    return Response(
        {"unread_count": get_unread_notification_count(request.user)},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def notification_mark_read_view(request, notification_id):
    """
    Mark one notification as read.

    POST /api/accounts/notifications/<notification_id>/mark-read/
    """
    notification = mark_notification_read(request.user, notification_id)

    if notification is None:
        return Response(
            {"detail": "Notification not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "detail": "Notification marked as read.",
            "notification": NotificationSerializer(notification).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def notification_mark_all_read_view(request):
    """
    Mark all user notifications as read.

    POST /api/accounts/notifications/mark-all-read/
    """
    updated_count = mark_all_notifications_read(request.user)

    return Response(
        {
            "detail": "All notifications marked as read.",
            "updated_count": updated_count,
            "unread_count": get_unread_notification_count(request.user),
        },
        status=status.HTTP_200_OK,
    )
