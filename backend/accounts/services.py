from secrets import randbelow

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import User, EmailOTP


def generate_otp_code():
    """Generate a secure 6-digit OTP code"""
    return f"{randbelow(1_000_000):06d}"


def create_email_verification_otp(user):
    """Create a new email verificaiton OTP for a user"""

    EmailOTP.objects.filter(
        user=user,
        purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
        is_used=False,
    ).update(is_used=True)

    otp = EmailOTP.objects.create(
        user=user,
        code=generate_otp_code(),
        purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
        expires_at=timezone.now()
        + timezone.timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )

    send_email_verification_otp(user, otp)

    return otp


def send_email_verification_otp(user, otp):
    """Send email verification otp"""

    subject = "Verify your League OS email address"

    message = (
        f"Hello {user.first_name},\n\n"
        f"Your League OS verification code is: {otp.code}\n\n"
        f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n\n"
        "If you did not request this code, please ignore this email.\n\n"
        "League OS Team"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify_email_otp(email, code):
    """Verify a user's email OTP"""
    normalized_email = email.strip().lower()
    normalized_code = code.strip()

    user = User.objects.filter(email__iexact=normalized_email).first()

    if user is None:
        raise ValidationError({"email": "No user exists with this email address."})

    if user.is_email_verified:
        return user

    otp = (
        EmailOTP.objects.filter(
            user=user,
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if otp is None:
        raise ValidationError(
            {"code": "No active OTP found. Please request a new one."}
        )

    if otp.is_expired:
        otp.is_used = True
        otp.save(update_fields=["is_used", "updated_at"])
        raise ValidationError({"code": "OTP has expired. Please request a new one."})

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp.is_used = True
        otp.save(update_fields=["is_used", "updated_at"])
        raise ValidationError(
            {"code": "Maximum OTP attempts exceeded. Please request a new one."}
        )

    if otp.code != normalized_code:
        otp.attempts += 1
        otp.save(update_fields=["attempts", "updated_at"])
        raise ValidationError({"code": "Invalid OTP code."})

    otp.is_used = True
    otp.save(update_fields=["is_used", "updated_at"])

    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])

    return user


def resend_email_verification_otp(email):
    """
    Create and send a new email verification OTP for an existing user.
    """

    normalized_email = email.strip().lower()

    user = User.objects.filter(email__iexact=normalized_email).first()

    if user is None:
        raise ValidationError({"email": "No user exists with this email address."})

    if user.is_email_verified:
        raise ValidationError({"email": "This email address is already verified."})

    return create_email_verification_otp(user)
