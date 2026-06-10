from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyOTPSerializer,
    ResendOTPSerializer,
)
from .services import (
    create_email_verification_otp,
    resend_email_verification_otp,
    verify_email_otp,
)


def get_dashboard_route(user):
    """Return the frontend dashboard route for a user role."""

    role_routes = {
        "FAN": "/dashboard/fan",
        "CLUB_ADMIN": "/dashboard/club-admin",
        "LEAGUE_ADMIN": "/dashboard/league-admin",
        "UNION_ADMIN": "/dashboard/union-admin",
        "SUPER_ADMIN": "/dashboard/super-admin",
        "REFEREE": "/dashboard/referee",
        "TICKETING_OFFICER": "/dashboard/ticketing-officer",
        "SPONSOR": "/dashboard/sponsor",
    }

    return role_routes.get(user.role, "/dashboard")


def get_backend_dashboard_route(user):
    """Return the backend dashboard API route for a user role."""

    role_routes = {
        "FAN": "/api/dashboards/fan/",
        "CLUB_ADMIN": "/api/dashboards/club-admin/",
        "LEAGUE_ADMIN": "/api/dashboards/league-admin/",
        "UNION_ADMIN": "/api/dashboards/union-admin/",
        "SUPER_ADMIN": "/api/dashboards/super-admin/",
        "REFEREE": "/api/dashboards/referee/",
        "TICKETING_OFFICER": "/api/dashboards/ticketing-officer/",
        "SPONSOR": "/api/dashboards/sponsor/",
    }

    return role_routes.get(user.role, "/api/dashboards/")


def build_token_response(user):
    """Build a JWT token response for a successfully authenticated user."""

    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@api_view(["POST"])
def register_view(request):
    """Register a new user and send an email verification OTP"""

    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        create_email_verification_otp(user)

        return Response(
            {
                "message": (
                    "Registration successful. Please verify your email address "
                    "using the OTP sent to your email."
                ),
                "requires_email_verification": not user.is_email_verified,
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
        tokens = build_token_response(user)

        return Response(
            {
                "message": "Login successful.",
                **tokens,
                "token_type": "Bearer",
                "user": UserSerializer(user, context={"request": request}).data,
                "role": user.role,
                "dashboard_route": get_dashboard_route(user),
                "backend_dashboard_route": get_backend_dashboard_route(user),
                "requires_email_verification": not user.is_email_verified,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
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
        user = verify_email_otp(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
        )

        return Response(
            {
                "message": "OTP verified successfully.",
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
        resend_email_verification_otp(email=serializer.validated_data["email"])

        return Response(
            {
                "message": "A new OTP has been sent to your email address.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
