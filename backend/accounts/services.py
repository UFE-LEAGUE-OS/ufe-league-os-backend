"""Services for accounts app - OTP handling, feed aggregation, wallet operations."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q

from .models import (
    Notification,
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

    _send_otp_email(user, code, purpose)
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


def _send_otp_email(user, code, purpose):
    """Send an OTP email when email sending is enabled."""

    if not getattr(settings, "SEND_OTP_EMAILS", False):
        return 0

    expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 10)

    if purpose == EmailOTP.Purpose.PASSWORD_RESET:
        subject = "Reset your League OS password"
        action_text = "password reset"
    else:
        subject = "Verify your League OS email address"
        action_text = "email verification"

    first_name = user.first_name or "there"

    message = (
        f"Hello {first_name},\n\n"
        f"Your League OS {action_text} code is: {code}\n\n"
        f"This code expires in {expiry_minutes} minutes.\n\n"
        "If you did not request this code, please ignore this email.\n\n"
        "League OS Team"
    )

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _print_otp_to_console(user, code, purpose):
    """Optionally print OTPs for local development only."""

    if not getattr(settings, "PRINT_DEV_OTPS", False):
        return

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
    """Get or create a wallet/payment center profile for a user."""
    wallet, _created = Wallet.objects.get_or_create(user=user)
    return wallet


def normalize_payment_status(status_value):
    """
    Normalize payment statuses from different apps into one frontend-friendly set.
    """

    value = str(status_value or "").strip().upper()

    if value in {"PAID", "CONFIRMED", "COMPLETED", "SUCCESSFUL", "SUCCESS"}:
        return "SUCCESSFUL"

    if value in {"PENDING", "PENDING_PAYMENT", "PROCESSING"}:
        return "PENDING"

    if value in {"FAILED", "REJECTED"}:
        return "FAILED"

    if value in {"CANCELLED", "CANCELED"}:
        return "CANCELLED"

    if value in {"REFUNDED", "PARTIALLY_REFUNDED"}:
        return "REFUNDED"

    return value or "UNKNOWN"


def payment_status_label(status_value):
    """Human-readable label for normalized payment statuses."""

    labels = {
        "SUCCESSFUL": "Successful",
        "PENDING": "Pending",
        "FAILED": "Failed",
        "CANCELLED": "Cancelled",
        "REFUNDED": "Refunded",
        "UNKNOWN": "Unknown",
    }
    return labels.get(status_value, status_value.replace("_", " ").title())


def _safe_decimal(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(Decimal("0.01"))


def _sort_payment_items(items):
    return sorted(
        items,
        key=lambda item: item.get("created_at")
        or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
        reverse=True,
    )


def _build_legacy_payment_items(user):
    items = []

    for payment in PaymentHistory.objects.filter(user=user):
        normalized_status = normalize_payment_status(payment.status)

        items.append(
            {
                "id": f"legacy-{payment.id}",
                "source": "LEGACY",
                "source_id": payment.id,
                "payment_type": payment.payment_type,
                "payment_type_label": payment.get_payment_type_display(),
                "amount": _safe_decimal(payment.amount),
                "currency": payment.currency,
                "status": normalized_status,
                "status_label": payment_status_label(normalized_status),
                "reference": payment.reference,
                "description": payment.description,
                "metadata": payment.metadata or {},
                "created_at": payment.created_at,
            }
        )

    return items


def _build_ticket_payment_items(user):
    items = []

    try:
        from ticketing.models import TicketOrder
    except ImportError:
        return items

    orders = (
        TicketOrder.objects.filter(buyer=user)
        .prefetch_related("items", "items__ticket_type", "tickets")
        .order_by("-created_at")
    )

    for order in orders:
        normalized_status = normalize_payment_status(order.status)

        description_parts = []
        for item in order.items.all():
            try:
                description_parts.append(
                    f"{item.ticket_type.match} - {item.ticket_type.name} x {item.quantity}"
                )
            except AttributeError:
                description_parts.append(f"{item.ticket_type.name} x {item.quantity}")

        description = "; ".join(description_parts) or f"Ticket order #{order.id}"

        items.append(
            {
                "id": f"ticket-order-{order.id}",
                "source": "TICKETING",
                "source_id": order.id,
                "payment_type": "TICKET_PURCHASE",
                "payment_type_label": "Ticket Purchase",
                "amount": _safe_decimal(order.total_amount),
                "currency": order.currency,
                "status": normalized_status,
                "status_label": payment_status_label(normalized_status),
                "reference": order.payment_reference,
                "description": description,
                "metadata": {
                    "provider": order.provider,
                    "provider_status": order.provider_status,
                    "tickets_count": order.tickets.count(),
                    "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                },
                "created_at": order.created_at,
            }
        )

    return items


def _build_membership_payment_items(user):
    items = []

    try:
        from memberships.models import MembershipPayment
    except ImportError:
        return items

    payments = (
        MembershipPayment.objects.filter(subscription__user=user)
        .select_related(
            "subscription",
            "subscription__club",
            "subscription__plan",
            "subscription_plan",
        )
        .order_by("-created_at")
    )

    for payment in payments:
        normalized_status = normalize_payment_status(payment.status)
        plan = payment.subscription_plan or payment.subscription.plan
        club = payment.subscription.club

        items.append(
            {
                "id": f"membership-payment-{payment.id}",
                "source": "MEMBERSHIPS",
                "source_id": payment.id,
                "payment_type": "MEMBERSHIP_FEE",
                "payment_type_label": "Membership Fee",
                "amount": _safe_decimal(payment.amount_paid),
                "currency": payment.currency,
                "status": normalized_status,
                "status_label": payment_status_label(normalized_status),
                "reference": payment.transaction_reference,
                "description": f"{club.name} - {plan.name}",
                "metadata": {
                    "club_id": club.id,
                    "club": club.name,
                    "plan_id": plan.id,
                    "plan": plan.name,
                    "subscription_id": payment.subscription_id,
                    "subscription_status": payment.subscription.status,
                    "provider": payment.provider,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                },
                "created_at": payment.created_at,
            }
        )

    return items


def _build_sponsorship_payment_items(user):
    items = []

    try:
        from sponsorships.models import SponsorPayment
    except ImportError:
        return items

    payments = (
        SponsorPayment.objects.filter(
            Q(agreement__sponsor_account__owner=user)
            | Q(agreement__sponsor_account__members__user=user)
            & Q(agreement__sponsor_account__members__is_active=True)
        )
        .select_related(
            "agreement",
            "agreement__sponsor_account",
            "agreement__sponsor_package",
        )
        .distinct()
        .order_by("-created_at")
    )

    for payment in payments:
        normalized_status = normalize_payment_status(payment.status)
        agreement = payment.agreement
        sponsor_account = agreement.sponsor_account
        sponsor_package = agreement.sponsor_package

        items.append(
            {
                "id": f"sponsor-payment-{payment.id}",
                "source": "SPONSORSHIPS",
                "source_id": payment.id,
                "payment_type": "SPONSORSHIP",
                "payment_type_label": "Sponsorship",
                "amount": _safe_decimal(payment.amount_paid),
                "currency": payment.currency,
                "status": normalized_status,
                "status_label": payment_status_label(normalized_status),
                "reference": payment.transaction_reference,
                "description": f"{sponsor_account.name} - {sponsor_package.name}",
                "metadata": {
                    "sponsor_account_id": sponsor_account.id,
                    "sponsor_account": sponsor_account.name,
                    "sponsor_type": sponsor_account.sponsor_type,
                    "agreement_id": agreement.id,
                    "agreement_status": agreement.status,
                    "sponsor_package_id": sponsor_package.id,
                    "sponsor_package": sponsor_package.name,
                    "provider": payment.provider,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "confirmed_at": (
                        payment.confirmed_at.isoformat()
                        if payment.confirmed_at
                        else None
                    ),
                },
                "created_at": payment.created_at,
            }
        )

    return items


def _build_ticket_wallet_items(user):
    tickets = []

    try:
        from ticketing.models import Ticket
    except ImportError:
        return tickets

    queryset = (
        Ticket.objects.filter(owner=user)
        .select_related("order", "ticket_type", "match")
        .order_by("-issued_at")
    )

    for ticket in queryset:
        tickets.append(
            {
                "id": ticket.id,
                "match": str(ticket.match),
                "match_id": ticket.match_id,
                "match_date": ticket.match.match_date,
                "venue": ticket.match.venue,
                "ticket_type": ticket.ticket_type.name,
                "amount_paid": _safe_decimal(ticket.ticket_type.price),
                "currency": ticket.ticket_type.currency,
                "status": ticket.status,
                "payment_status": ticket.order.status,
                "ticket_code": str(ticket.ticket_code),
                "qr_payload": ticket.qr_payload,
                "issued_at": ticket.issued_at,
                "used_at": ticket.used_at,
            }
        )

    return tickets


def _build_membership_wallet_items(user):
    memberships = []

    try:
        from memberships.models import MembershipSubscription
    except ImportError:
        return memberships

    queryset = (
        MembershipSubscription.objects.filter(user=user)
        .select_related("club", "plan")
        .order_by("-created_at")
    )

    for subscription in queryset:
        latest_payment = subscription.payments.order_by("-created_at").first()

        memberships.append(
            {
                "id": subscription.id,
                "club": subscription.club.name,
                "club_id": subscription.club_id,
                "membership_tier": subscription.plan.tier,
                "membership_plan": subscription.plan.name,
                "amount_paid": (
                    _safe_decimal(latest_payment.amount_paid)
                    if latest_payment
                    else Decimal("0.00")
                ),
                "currency": subscription.plan.currency,
                "status": subscription.status,
                "payment_status": latest_payment.status if latest_payment else None,
                "valid_from": subscription.starts_at,
                "valid_until": subscription.ends_at,
            }
        )

    return memberships


def _build_sponsorship_wallet_items(user):
    sponsorships = []

    try:
        from sponsorships.models import SponsorPayment
    except ImportError:
        return sponsorships

    queryset = (
        SponsorPayment.objects.filter(
            Q(agreement__sponsor_account__owner=user)
            | Q(agreement__sponsor_account__members__user=user)
            & Q(agreement__sponsor_account__members__is_active=True)
        )
        .select_related(
            "agreement",
            "agreement__sponsor_account",
            "agreement__sponsor_package",
        )
        .distinct()
        .order_by("-created_at")
    )

    for payment in queryset:
        agreement = payment.agreement
        sponsor_account = agreement.sponsor_account
        sponsor_package = agreement.sponsor_package

        sponsorships.append(
            {
                "id": payment.id,
                "sponsor_account": sponsor_account.name,
                "sponsor_type": sponsor_account.sponsor_type,
                "campaign": sponsor_package.name,
                "amount_paid": _safe_decimal(payment.amount_paid),
                "currency": payment.currency,
                "status": payment.status,
                "provider": payment.provider,
                "reference": payment.transaction_reference,
                "paid_at": payment.paid_at,
                "created_at": payment.created_at,
            }
        )

    return sponsorships


def get_combined_payment_history(
    user,
    payment_type=None,
    status=None,
    source=None,
    limit=50,
    offset=0,
):
    """
    Get combined payment history across legacy payment records, tickets,
    memberships, and sponsorships.
    """

    items = []
    items.extend(_build_legacy_payment_items(user))
    items.extend(_build_ticket_payment_items(user))
    items.extend(_build_membership_payment_items(user))
    items.extend(_build_sponsorship_payment_items(user))

    if payment_type:
        items = [
            item
            for item in items
            if item["payment_type"].upper() == str(payment_type).upper()
        ]

    if status:
        items = [
            item
            for item in items
            if item["status"].upper() == str(status).upper()
            or item["status"].upper() == normalize_payment_status(status)
        ]

    if source:
        items = [
            item for item in items if item["source"].upper() == str(source).upper()
        ]

    items = _sort_payment_items(items)
    total = len(items)

    return items[offset : offset + limit], total


def get_payment_history(user, payment_type=None, status=None, limit=50, offset=0):
    """
    Backwards-compatible payment history service.

    Now returns the combined MVP payment history instead of only legacy records.
    """
    return get_combined_payment_history(
        user=user,
        payment_type=payment_type,
        status=status,
        limit=limit,
        offset=offset,
    )


def get_wallet_payment_center(user, limit=10):
    """
    Build the MVP wallet/payment center response.

    The MVP wallet does not store money. It summarizes payments and paid items.
    """

    wallet = get_or_create_wallet(user)
    payment_items, _total = get_combined_payment_history(user, limit=1000, offset=0)

    successful_items = [
        item for item in payment_items if item["status"] == "SUCCESSFUL"
    ]
    pending_items = [item for item in payment_items if item["status"] == "PENDING"]
    failed_items = [item for item in payment_items if item["status"] == "FAILED"]
    refunded_items = [item for item in payment_items if item["status"] == "REFUNDED"]

    tickets = _build_ticket_wallet_items(user)
    memberships = _build_membership_wallet_items(user)
    sponsorships = _build_sponsorship_wallet_items(user)

    total_spent = sum(
        (_safe_decimal(item["amount"]) for item in successful_items),
        Decimal("0.00"),
    )

    return {
        "stored_balance_enabled": wallet.stored_balance_enabled,
        "balance": _safe_decimal(wallet.balance),
        "balance_note": wallet.balance_note,
        "currency": wallet.currency,
        "total_spent": total_spent,
        "successful_payments_count": len(successful_items),
        "pending_payments_count": len(pending_items),
        "failed_payments_count": len(failed_items),
        "refunded_payments_count": len(refunded_items),
        "tickets_count": len(tickets),
        "memberships_count": len(memberships),
        "sponsorships_count": len(sponsorships),
        "recent_payments": payment_items[:limit],
        "tickets": tickets[:limit],
        "memberships": memberships[:limit],
        "sponsorships": sponsorships[:limit],
    }


def user_allows_notification(user, event_type, channel="push"):
    """
    Check whether a user allows a notification event/channel.

    For the frontend inbox, we treat push_enabled as the in-app notification toggle.
    """
    pref, _created = NotificationPreference.objects.get_or_create(
        user=user,
        event_type=event_type,
    )

    if channel == "email":
        return pref.email_enabled

    if channel == "sms":
        return pref.sms_enabled

    return pref.push_enabled


def create_in_app_notification(
    user,
    event_type,
    title,
    message="",
    category=Notification.Category.SYSTEM,
    priority=Notification.Priority.NORMAL,
    action_url="",
    metadata=None,
):
    """
    Create an in-app notification if the user's in-app/push preference allows it.
    """
    metadata = metadata or {}

    if not user_allows_notification(user, event_type, channel="push"):
        return None

    return Notification.objects.create(
        user=user,
        event_type=event_type,
        category=category,
        priority=priority,
        title=title,
        message=message,
        action_url=action_url,
        metadata=metadata,
    )


def list_user_notifications(
    user,
    limit=50,
    offset=0,
    unread_only=False,
    category=None,
):
    queryset = Notification.objects.filter(user=user).order_by("-created_at")

    if unread_only:
        queryset = queryset.filter(is_read=False)

    if category:
        queryset = queryset.filter(category=str(category).upper())

    total = queryset.count()
    items = queryset[offset : offset + limit]

    return items, total


def get_unread_notification_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()


def mark_notification_read(user, notification_id):
    notification = Notification.objects.filter(id=notification_id, user=user).first()

    if notification is None:
        return None

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])

    return notification


def mark_all_notifications_read(user):
    now = timezone.now()

    return Notification.objects.filter(user=user, is_read=False).update(
        is_read=True,
        read_at=now,
    )
