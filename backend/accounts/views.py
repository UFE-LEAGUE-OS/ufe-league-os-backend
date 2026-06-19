import logging
from smtplib import SMTPException

from django.core.mail import BadHeaderError
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import (
    IsAuthenticatedAudit,
    IsSuperAdmin,
    IsClubAdmin,
    IsLeagueAdmin,
    IsUnionAdmin,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Club, User
from .serializers import (
    AdminCreateUserSerializer,
    HierarchicalCreateUserSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyOTPSerializer,
    ResendOTPSerializer,
    ProfileUpdateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .rbac import (
    get_backend_dashboard_route,
    get_dashboard_route,
    get_dashboard_routes,
    log_role_change,
)
from .services import (
    create_email_verification_otp,
    resend_email_verification_otp,
    verify_email_otp,
    request_password_reset_otp,
    reset_password_with_otp,
)
from sponsorships.serializers import (
    SponsorAccountCreateSerializer,
    SponsorAccountSerializer,
)

logger = logging.getLogger(__name__)


class AuthNextStep:
    """Frontend nvaigation hints for authentication responses."""

    VERIFY_EMAIL = "VERIFY_EMAIL"
    LOGIN = "LOG_IN"
    DASHBOARD = "DASHBOARD"
    RESET_PASSWORD = "RESET_PASSWORD"
    REQUEST_NEW_OTP = "REQUEST_NEW_OTP"


@api_view(["GET"])
def roles_view(request):
    """Return all available user roles."""
    roles = [{"key": choice[0], "label": choice[1]} for choice in User.Role.choices]
    return Response({"roles": roles})


def build_token_response(user):
    """Build a JWT token response for a successfully authenticated user."""

    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@api_view(["POST"])
def register_view(request):
    """Register a new user and send an email verification OTP."""

    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        try:
            with transaction.atomic():
                user = serializer.save()
                create_email_verification_otp(user)
        except (SMTPException, OSError, BadHeaderError) as exc:
            logger.exception("Registration OTP email delivery failed: %s", exc)
            return Response(
                {
                    "detail": (
                        "Registration could not be completed because the "
                        "verification email could not be sent. Please try again."
                    ),
                    "code": "verification_email_failed",
                    "next_step": AuthNextStep.REQUEST_NEW_OTP,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "Registration successful. Please verify your email address "
                    "using the OTP sent to your email."
                ),
                "requires_email_verification": not user.is_email_verified,
                "next_step": AuthNextStep.VERIFY_EMAIL,
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def login_view(request):
    """Log in with email or phone number and return JWT tokens."""

    serializer = LoginSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.validated_data["user"]

        if not user.is_email_verified:
            return Response(
                {
                    "detail": "Please verify your email address before logging in.",
                    "code": "email_not_verified",
                    "requires_email_verification": True,
                    "next_step": AuthNextStep.VERIFY_EMAIL,
                    "email": user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = build_token_response(user)

        return Response(
            {
                "message": "Login successful.",
                **tokens,
                "token_type": "Bearer",
                "user": UserSerializer(user, context={"request": request}).data,
                "role": user.role,
                "frontend_dashboard_route": get_dashboard_route(user),
                "backend_dashboard_route": get_backend_dashboard_route(user),
                "requires_email_verification": not user.is_email_verified,
                "next_step": AuthNextStep.DASHBOARD,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def me_view(request):
    """Return the currently authenticated user."""

    return Response(
        UserSerializer(request.user, context={"request": request}).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def verify_otp_view(request):
    """Verify a user's email OTP."""

    serializer = VerifyOTPSerializer(data=request.data)

    if serializer.is_valid():
        try:
            user = verify_email_otp(
                email=serializer.validated_data["email"],
                code=serializer.validated_data["code"],
            )
        except (ValueError, User.DoesNotExist) as e:
            return Response({"code": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "OTP verified successfully.",
                "requires_email_verification": False,
                "next_step": AuthNextStep.LOGIN,
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def resend_otp_view(request):
    """Resend an email verification OTP."""

    serializer = ResendOTPSerializer(data=request.data)

    if serializer.is_valid():
        try:
            resend_email_verification_otp(email=serializer.validated_data["email"])
        except (ValueError, User.DoesNotExist) as e:
            return Response({"email": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "A new OTP has been sent to your email address.",
                "next_step": AuthNextStep.VERIFY_EMAIL,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def password_reset_request_view(request):
    """Request a password reset OTP."""

    serializer = PasswordResetRequestSerializer(data=request.data)

    if serializer.is_valid():
        try:
            request_password_reset_otp(email=serializer.validated_data["email"])
        except (ValueError, User.DoesNotExist) as e:
            return Response({"email": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "A password reset OTP has been sent to your email address.",
                "next_step": AuthNextStep.RESET_PASSWORD,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def password_reset_confirm_view(request):
    """Reset password using a valid password reset OTP."""

    serializer = PasswordResetConfirmSerializer(data=request.data)

    if serializer.is_valid():
        try:
            reset_password_with_otp(
                email=serializer.validated_data["email"],
                code=serializer.validated_data["code"],
                new_password=serializer.validated_data["password"],
            )
        except (ValueError, User.DoesNotExist) as e:
            return Response({"code": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "Password reset successful. You can now log in.",
                "next_step": AuthNextStep.LOGIN,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def profile_view(request):
    """Retrieve or update the authenticated user's profile."""

    if request.method == "GET":
        return Response(
            UserSerializer(request.user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    serializer = ProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=True,
        context={"request": request},
    )

    if serializer.is_valid():
        user = serializer.save()

        return Response(
            {
                "message": "Profile updated successfully.",
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticatedAudit])
def remove_avatar_view(request):
    """Remove the authenticated user's avatar."""

    user = request.user

    if user.avatar:
        user.avatar.delete(save=False)
        user.avatar = None
        user.save(update_fields=["avatar"])

    return Response(
        {
            "message": "Avatar removed successfully.",
            "user": UserSerializer(user, context={"request": request}).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def become_sponsor_view(request):
    """
    Create a proper sponsor account for an existing user.

    This endpoint is kept as a shortcut/backward-compatible route.
    The real sponsorship source of truth is:
    - SponsorAccount
    - SponsorAccountMember

    User.is_sponsor is only updated as a legacy helper flag.
    """

    serializer = SponsorAccountCreateSerializer(
        data=request.data,
        context={"request": request},
    )

    if serializer.is_valid():
        sponsor_account = serializer.save()
        user = request.user

        update_fields = []

        if not user.is_sponsor:
            user.is_sponsor = True
            update_fields.append("is_sponsor")

        if user.sponsor_type != sponsor_account.sponsor_type:
            user.sponsor_type = sponsor_account.sponsor_type
            update_fields.append("sponsor_type")

        if update_fields:
            user.save(update_fields=update_fields)

        return Response(
            {
                "message": "Sponsor account created successfully.",
                "user": UserSerializer(user, context={"request": request}).data,
                "sponsor_account": SponsorAccountSerializer(
                    sponsor_account,
                    context={"request": request},
                ).data,
                "dashboard_routes": get_dashboard_routes(user),
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsSuperAdmin])
def superadmin_create_user_view(request):
    """Allow a superadmin to create a new authenticated user with a role."""

    serializer = AdminCreateUserSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    club = None
    if validated.get("club_id"):
        club = Club.objects.filter(pk=validated["club_id"]).first()

    user = User.objects.create_user(
        email=validated["email"],
        password=validated["password"],
        phone_number=validated.get("phone_number"),
        first_name=validated["first_name"].strip(),
        last_name=validated["last_name"].strip(),
        role=validated["role"],
        club=club,
    )

    log_role_change(
        target_user=user,
        previous_role=None,
        new_role=user.role,
        actor=request.user,
        reason="superadmin_create",
    )

    return Response(
        {
            "message": "User created successfully.",
            "user": UserSerializer(user, context={"request": request}).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _create_user_by_admin(request, reason_prefix):
    """
    Shared helper for admin-level user creation views.
    Uses HierarchicalCreateUserSerializer which validates the target role
    against the calling admin's role hierarchy.
    """
    serializer = HierarchicalCreateUserSerializer(
        data=request.data,
        context={"admin_user": request.user},
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    club = None
    if validated.get("club_id"):
        club = Club.objects.filter(pk=validated["club_id"]).first()

    user = User.objects.create_user(
        email=validated["email"],
        password=validated["password"],
        phone_number=validated.get("phone_number"),
        first_name=validated["first_name"].strip(),
        last_name=validated["last_name"].strip(),
        role=validated["role"],
        club=club,
    )

    log_role_change(
        target_user=user,
        previous_role=None,
        new_role=user.role,
        actor=request.user,
        reason=f"{reason_prefix}_create",
    )

    return Response(
        {
            "message": "User created successfully.",
            "user": UserSerializer(user, context={"request": request}).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsUnionAdmin])
def union_admin_create_user_view(request):
    """
    Allow a union admin to create a user.
    Can create: REFEREE, TICKETING_OFFICER
    """
    return _create_user_by_admin(request, "union_admin")


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsLeagueAdmin])
def league_admin_create_user_view(request):
    """
    Allow a league admin to create a user.
    Can create: CLUB_ADMIN, REFEREE, TICKETING_OFFICER
    """
    return _create_user_by_admin(request, "league_admin")


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsClubAdmin])
def club_admin_create_user_view(request):
    """
    Allow a club admin to create a user.
    Can create: TICKETING_OFFICER
    """
    return _create_user_by_admin(request, "club_admin")
