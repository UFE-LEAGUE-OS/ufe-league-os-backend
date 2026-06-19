"""Services for accounts app - OTP handling, feed aggregation, wallet operations."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import (
    EmailOTP,
    FeedItem,
    Follow,
    InterestPreference,
    NotificationPreference,
    PaymentHistory,
    User,
    Wallet,
)

# ---------------------------------------------------------------------------
# OTP Services
# ---------------------------------------------------------------------------


def create_email_verification_otp(user, purpose=EmailOTP.Purpose.EMAIL_VERIFICATION):
    """Create an OTP for the given user and purpose."""
    from random import randint

    expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 10)

    code = f"{randint(100000, 999999)}"

    otp = EmailOTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )

    _print_otp_to_console(user, code, purpose.lower().replace("_", " "))

    return otp


def resend_email_verification_otp(email):
    """Invalidate existing unused OTPs and create a new email verification OTP."""

    user = User.objects.get(email__iexact=email)

    if user.is_email_verified:
        raise ValueError("Email is already verified.")

    EmailOTP.objects.filter(
        user=user,
        purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
        is_used=False,
    ).update(is_used=True)

    return create_email_verification_otp(user)


def verify_email_otp(email, code):
    """Verify the OTP code for email verification."""

    max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)

    user = User.objects.get(email__iexact=email)

    try:
        otp = EmailOTP.objects.filter(
            user=user,
            code=code,
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            is_used=False,
        ).latest("created_at")
    except EmailOTP.DoesNotExist:
        # Increment attempts on the latest unused OTP for this purpose
        latest_otp = (
            EmailOTP.objects.filter(
                user=user, purpose=EmailOTP.Purpose.EMAIL_VERIFICATION, is_used=False
            )
            .order_by("-created_at")
            .first()
        )

        if latest_otp:
            latest_otp.attempts += 1
            if latest_otp.attempts >= max_attempts:
                latest_otp.is_used = True
            latest_otp.save(update_fields=["attempts", "is_used"])
        raise ValueError("Invalid OTP code.")

    if otp.is_expired:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise ValueError("OTP has expired.")

    if otp.attempts >= max_attempts:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise ValueError("OTP has been locked due to too many failed attempts.")

    # Successful verification
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])

    return user


def request_password_reset_otp(email):
    """Request a password reset OTP."""

    user = User.objects.get(email__iexact=email)

    EmailOTP.objects.filter(
        user=user,
        purpose=EmailOTP.Purpose.PASSWORD_RESET,
        is_used=False,
    ).update(is_used=True)

    return create_email_verification_otp(user, purpose=EmailOTP.Purpose.PASSWORD_RESET)


def reset_password_with_otp(email, code, new_password):
    """Reset the password using a valid password reset OTP."""

    max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)

    user = User.objects.get(email__iexact=email)

    try:
        otp = EmailOTP.objects.filter(
            user=user,
            code=code,
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            is_used=False,
        ).latest("created_at")
    except EmailOTP.DoesNotExist:
        # Increment attempts on the latest unused OTP for this purpose
        latest_otp = (
            EmailOTP.objects.filter(
                user=user, purpose=EmailOTP.Purpose.PASSWORD_RESET, is_used=False
            )
            .order_by("-created_at")
            .first()
        )

        if latest_otp:
            latest_otp.attempts += 1
            if latest_otp.attempts >= max_attempts:
                latest_otp.is_used = True
            latest_otp.save(update_fields=["attempts", "is_used"])
        raise ValueError("Invalid OTP code.")

    if otp.is_expired:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise ValueError("OTP has expired.")

    if otp.attempts >= max_attempts:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise ValueError("OTP has been locked due to too many failed attempts.")

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    user.set_password(new_password)
    user.save(update_fields=["password"])

    return user


def _print_otp_to_console(user, code, purpose):
    """Print OTP to console for development/testing."""
    print("=" * 60)
    print(f"DEV OTP for {user.email}: {code} ({purpose})")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Follow / Unfollow Services
# ---------------------------------------------------------------------------


def follow_entity(user, content_type, object_id):
    """Create a follow relationship. Returns (follow, created) tuple."""
    follow, created = Follow.objects.get_or_create(
        user=user,
        content_type=content_type,
        object_id=object_id,
    )
    return follow, created


def unfollow_entity(user, content_type, object_id):
    """Remove a follow relationship. Returns True if deleted, False if not found."""
    deleted, _ = Follow.objects.filter(
        user=user,
        content_type=content_type,
        object_id=object_id,
    ).delete()
    return deleted > 0


def get_user_follows(user):
    """Get all follows for a user, grouped by content type."""
    follows = Follow.objects.filter(user=user).select_related("user")

    clubs = []
    leagues = []
    unions = []
    competitions = []

    for f in follows:
        obj = f.followed_object
        name = str(obj) if obj else f"{f.content_type}#{f.object_id}"
        data = {
            "id": f.id,
            "content_type": f.content_type,
            "object_id": f.object_id,
            "object_name": name,
            "created_at": f.created_at,
        }
        if f.content_type == Follow.ContentType.CLUB:
            clubs.append(data)
        elif f.content_type == Follow.ContentType.LEAGUE:
            leagues.append(data)
        elif f.content_type == Follow.ContentType.UNION:
            unions.append(data)
        elif f.content_type == Follow.ContentType.COMPETITION:
            competitions.append(data)

    return {
        "club_count": len(clubs),
        "league_count": len(leagues),
        "union_count": len(unions),
        "competition_count": len(competitions),
        "clubs": clubs,
        "leagues": leagues,
        "unions": unions,
        "competitions": competitions,
    }


def is_following(user, content_type, object_id):
    """Check if a user follows a specific entity."""
    return Follow.objects.filter(
        user=user, content_type=content_type, object_id=object_id
    ).exists()


# ---------------------------------------------------------------------------
# Feed Aggregation Service
# ---------------------------------------------------------------------------


def aggregate_feed(user, limit=50, offset=0, item_type=None, unread_only=False):
    """
    Generate a personalized feed for a user based on their follows and interests.

    The feed is ranked by relevance_score descending, then by created_at descending.
    Supports filtering by item_type and unread_only.
    """
    queryset = FeedItem.objects.filter(user=user)

    if item_type:
        queryset = queryset.filter(item_type=item_type)

    if unread_only:
        queryset = queryset.filter(is_read=False)

    queryset = queryset.order_by("-relevance_score", "-created_at")

    total_count = queryset.count()
    items = queryset[offset : offset + limit]

    return items, total_count


def create_feed_item(
    user,
    item_type,
    title,
    description="",
    source_content_type="",
    source_object_id=None,
    source_name="",
    relevance_score=0.0,
    link="",
    metadata=None,
):
    """Create a feed item for a user."""
    feed_item = FeedItem.objects.create(
        user=user,
        item_type=item_type,
        title=title,
        description=description,
        source_content_type=source_content_type,
        source_object_id=source_object_id,
        source_name=source_name,
        relevance_score=relevance_score,
        link=link,
        metadata=metadata or {},
    )
    return feed_item


def mark_feed_item_read(user, feed_item_id):
    """Mark a single feed item as read."""
    updated = FeedItem.objects.filter(id=feed_item_id, user=user).update(is_read=True)
    return updated > 0


def mark_all_feed_read(user):
    """Mark all feed items as read for a user."""
    updated = FeedItem.objects.filter(user=user, is_read=False).update(is_read=True)
    return updated


def get_unread_feed_count(user):
    """Get count of unread feed items."""
    return FeedItem.objects.filter(user=user, is_read=False).count()


# ---------------------------------------------------------------------------
# Notification Preference Services
# ---------------------------------------------------------------------------


def get_or_create_notification_preferences(user):
    """Get or create all default notification preferences for a user."""
    defaults = []
    for event_type, _label in NotificationPreference.EventType.choices:
        pref, _created = NotificationPreference.objects.get_or_create(
            user=user, event_type=event_type
        )
        defaults.append(pref)
    return defaults


# ---------------------------------------------------------------------------
# Interest & Privacy Preference Services
# ---------------------------------------------------------------------------


def get_or_create_interest_preferences(user):
    """Get or create interest/privacy preferences for a user."""
    pref, _created = InterestPreference.objects.get_or_create(user=user)
    return pref


# ---------------------------------------------------------------------------
# Wallet & Payment History Services
# ---------------------------------------------------------------------------


def get_or_create_wallet(user):
    """Get or create a wallet for a user."""
    wallet, _created = Wallet.objects.get_or_create(user=user)
    return wallet


def get_payment_history(user, payment_type=None, status=None, limit=50, offset=0):
    """Get payment history for a user with optional filters."""
    queryset = PaymentHistory.objects.filter(user=user)

    if payment_type:
        queryset = queryset.filter(payment_type=payment_type)

    if status:
        queryset = queryset.filter(status=status)

    total = queryset.count()
    items = queryset.order_by("-created_at")[offset : offset + limit]
    return items, total
