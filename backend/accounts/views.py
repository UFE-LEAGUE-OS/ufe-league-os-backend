import logging
from smtplib import SMTPException

from django.core.mail import BadHeaderError
from django.db import transaction
from django.conf import settings
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
from accounts.models import RoleApproval
from rest_framework_simplejwt.tokens import RefreshToken

from .google_auth import (
    GoogleAuthException,
    GoogleEmailNotVerifiedError,
    InvalidGoogleTokenError,
    extract_google_user_info,
    verify_google_id_token,
)
from .models import Club, User
from .serializers import (
    AdminCreateUserSerializer,
    GoogleAuthSerializer,
    HierarchicalCreateUserSerializer,
    LoginSerializer,
    RegisterSerializer,
    RoleApprovalListSerializer,
    RoleApprovalReviewSerializer,
    SwitchWorkspaceSerializer,
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
    is_sensitive_role,
    create_role_approval,
    approve_role_approval,
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
def config_view(request):
    """
    Return frontend-facing configuration including auth provider status.

    Frontend uses this to determine whether to show Google Sign-In button.
    """
    client_id = getattr(settings, "GOOGLE_OAUTH2_CLIENT_ID", "")
    return Response(
        {
            "google_oauth": {
                "enabled": bool(client_id),
                "client_id": client_id,
            }
        }
    )


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


@api_view(["POST"])
def google_auth_view(request):
    """
    Authenticate or register a user using a Google ID token.

    Flow:
    1. Frontend sends Google ID token obtained via Google Sign-In.
    2. Backend verifies the token using google-auth library.
    3. If a user with the Google email exists, log them in.
    4. If no user exists, create a new FAN account automatically.
    5. Return JWT tokens and user data (always marked as email_verified).

    Google accounts come with a verified email, so is_email_verified
    is set to True for both new and existing users.
    """

    serializer = GoogleAuthSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = verify_google_id_token(serializer.validated_data["id_token"])
    except InvalidGoogleTokenError as exc:
        return Response(
            {"id_token": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except GoogleEmailNotVerifiedError as exc:
        return Response(
            {"id_token": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except GoogleAuthException as exc:
        return Response(
            {"id_token": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_info = extract_google_user_info(payload)
    email = user_info["email"]
    first_name = user_info["first_name"]
    last_name = user_info["last_name"]

    # Check if user already exists
    user = User.objects.filter(email__iexact=email).first()

    if user:
        # Existing user — update profile fields from Google if empty
        update_fields = []

        if not user.first_name and first_name:
            user.first_name = first_name
            update_fields.append("first_name")

        if not user.last_name and last_name:
            user.last_name = last_name
            update_fields.append("last_name")

        # Mark email as verified (Google accounts have verified emails)
        if not user.is_email_verified:
            user.is_email_verified = True
            update_fields.append("is_email_verified")

        if update_fields:
            user.save(update_fields=update_fields)

        # Generate tokens
        tokens = build_token_response(user)

        return Response(
            {
                "message": "Google login successful.",
                "is_new_user": False,
                **tokens,
                "token_type": "Bearer",
                "user": UserSerializer(user, context={"request": request}).data,
                "role": user.role,
                "frontend_dashboard_route": get_dashboard_route(user),
                "backend_dashboard_route": get_backend_dashboard_route(user),
                "next_step": AuthNextStep.DASHBOARD,
            },
            status=status.HTTP_200_OK,
        )

    # New user — auto-register with Google data
    user = User.objects.create_user(
        email=email,
        password=None,  # No password needed — Google OAuth handles auth
        first_name=first_name,
        last_name=last_name,
        role=User.Role.FAN,
        is_email_verified=True,  # Google accounts have verified emails
    )

    tokens = build_token_response(user)

    return Response(
        {
            "message": "Google registration successful.",
            "is_new_user": True,
            **tokens,
            "token_type": "Bearer",
            "user": UserSerializer(user, context={"request": request}).data,
            "role": user.role,
            "frontend_dashboard_route": get_dashboard_route(user),
            "backend_dashboard_route": get_backend_dashboard_route(user),
            "next_step": AuthNextStep.DASHBOARD,
        },
        status=status.HTTP_201_CREATED,
    )


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
    """
    Allow a superadmin to create a new authenticated user.

    If the requested role is a sensitive role (UNION_ADMIN, SUPER_ADMIN),
    the role change is NOT applied immediately. Instead, a RoleApproval
    request is created in PENDING status. Another SUPER_ADMIN must approve
    it via the role-approval review endpoint before the role takes effect.

    Non-sensitive roles are applied immediately (existing behavior).
    """

    serializer = AdminCreateUserSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    role = validated["role"]

    club = None
    if validated.get("club_id"):
        club = Club.objects.filter(pk=validated["club_id"]).first()

    user = User.objects.create_user(
        email=validated["email"],
        password=validated["password"],
        phone_number=validated.get("phone_number"),
        first_name=validated["first_name"].strip(),
        last_name=validated["last_name"].strip(),
        role=User.Role.FAN,  # Always start as FAN; role will be applied after approval
        club=club,
    )

    if is_sensitive_role(role):
        # Sensitive role: create approval request instead of applying directly
        approval = create_role_approval(
            target_user=user,
            requested_role=role,
            requested_by=request.user,
            reason=validated.get("reason", "superadmin_create"),
        )

        return Response(
            {
                "message": (
                    f"User created successfully. A role approval request has been "
                    f"submitted for the '{role}' role. Another SUPER_ADMIN must "
                    f"approve this request before the role takes effect."
                ),
                "requires_approval": True,
                "approval": RoleApprovalListSerializer(approval).data,
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # Non-sensitive role: apply immediately
    user.role = role
    user.save(update_fields=["role"])

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


# ---------------------------------------------------------------------------
# Role Approval Endpoints
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit, IsSuperAdmin])
def role_approval_list_view(request):
    """
    GET: List all role approval requests.

    Filters:
    - status: Filter by status (PENDING, APPROVED, REJECTED)
    - target_user: Filter by target user ID
    """
    queryset = RoleApproval.objects.all()

    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter.upper())

    target_user = request.query_params.get("target_user")
    if target_user:
        queryset = queryset.filter(target_user_id=target_user)

    queryset = queryset.order_by("-created_at")
    serializer = RoleApprovalListSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit, IsSuperAdmin])
def role_approval_pending_count_view(request):
    """
    GET: Return the count of pending role approval requests.
    """
    count = RoleApproval.objects.filter(status=RoleApproval.Status.PENDING).count()
    return Response({"pending_count": count})


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsSuperAdmin])
def role_approval_review_view(request, pk):
    """
    POST: Approve or reject a role approval request.

    The reviewer must be a different SUPER_ADMIN than the requester.
    """
    try:
        approval = RoleApproval.objects.select_related(
            "target_user", "requested_by"
        ).get(pk=pk)
    except RoleApproval.DoesNotExist:
        return Response(
            {"detail": "Role approval request not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if approval.status != RoleApproval.Status.PENDING:
        return Response(
            {
                "detail": (
                    f"This request has already been {approval.status.lower()}."
                    " Only PENDING requests can be reviewed."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # A SUPER_ADMIN cannot approve their own request
    if approval.requested_by == request.user:
        return Response(
            {
                "detail": "You cannot approve or reject your own role approval request."
                " Another SUPER_ADMIN must review it."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = RoleApprovalReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    action = serializer.validated_data["action"]
    rejection_reason = serializer.validated_data.get("rejection_reason", "")

    try:
        approve_role_approval(
            approval=approval,
            reviewer=request.user,
            rejection_reason=rejection_reason if action == "reject" else "",
        )
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    action_label = "approved" if action == "approve" else "rejected"

    return Response(
        {
            "detail": f"Role approval request {action_label} successfully.",
            "approval": RoleApprovalListSerializer(approval).data,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Switch Workspace / Account API
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def switch_workspace_view(request):
    """
    POST: Switch the active workspace/role context for the authenticated user.

    Users with multiple roles (e.g., FAN + SPONSOR) can switch between their
    available workspaces to access role-specific dashboards and features.

    Request body:
        { "role": "SPONSOR" }

    Returns the dashboard route for the requested role.
    """
    from .rbac import FRONTEND_DASHBOARD_ROUTES, BACKEND_DASHBOARD_ROUTES

    serializer = SwitchWorkspaceSerializer(
        data=request.data,
        context={"user": request.user},
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    target_role = serializer.validated_data["role"]

    # The User model only has a single role field, but `user.roles` can include
    # additional roles like SPONSOR via `has_role`. The switch workspace API
    # returns the appropriate dashboard info for the requested role without
    # changing the user's primary role in the DB.
    return Response(
        {
            "message": f"Switched to {target_role} workspace.",
            "role": target_role,
            "role_display": dict(User.Role.choices).get(target_role, target_role),
            "frontend_dashboard_route": FRONTEND_DASHBOARD_ROUTES.get(
                target_role, "/dashboard/fan"
            ),
            "backend_dashboard_route": BACKEND_DASHBOARD_ROUTES.get(
                target_role, "/api/dashboards/me/"
            ),
            "available_dashboards": get_dashboard_routes(request.user),
            "user": UserSerializer(request.user, context={"request": request}).data,
        },
        status=status.HTTP_200_OK,
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
