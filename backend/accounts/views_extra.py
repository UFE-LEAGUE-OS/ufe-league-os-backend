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
    FeedItemSerializer,
    FollowActionSerializer,
    FollowResponseSerializer,
    InterestPreferenceSerializer,
    NotificationPreferenceSerializer,
    PaymentHistorySerializer,
    WalletSerializer,
)
from .services import (
    aggregate_feed,
    follow_entity,
    get_or_create_interest_preferences,
    get_or_create_notification_preferences,
    get_or_create_wallet,
    get_payment_history,
    get_user_follows,
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


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticatedAudit])
def notification_preferences_view(request):
    """
    Get or update the authenticated user's notification preferences.

    GET /api/accounts/notifications/          - List all preferences
    PUT /api/accounts/notifications/          - Bulk update preferences
    """
    user = request.user

    if request.method == "GET":
        prefs = get_or_create_notification_preferences(user)
        serializer = NotificationPreferenceSerializer(prefs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # PUT: bulk update
    data = request.data
    if isinstance(data, dict):
        data = [data]

    updated = []
    errors = []
    for pref_data in data:
        event_type = pref_data.get("event_type")
        if not event_type:
            errors.append({"error": "event_type is required for each preference."})
            continue

        pref, _ = NotificationPreference.objects.get_or_create(
            user=user, event_type=event_type
        )
        serializer = NotificationPreferenceSerializer(
            pref, data=pref_data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            updated.append(serializer.data)
        else:
            errors.append(serializer.errors)

    response_data = {"updated": updated}
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
    Get the authenticated user's wallet.

    GET /api/accounts/wallet/          - Get wallet
    """
    user = request.user
    wallet = get_or_create_wallet(user)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Payment History API
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def payment_history_view(request):
    """
    Get the authenticated user's payment history.

    GET /api/accounts/payments/          - List payments
    Query params: payment_type, status, limit, offset
    """
    user = request.user
    payment_type = request.query_params.get("payment_type")
    status_filter = request.query_params.get("status")
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))

    items, total = get_payment_history(
        user,
        payment_type=payment_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    serializer = PaymentHistorySerializer(items, many=True)
    return Response(
        {
            "count": total,
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
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
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
