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
    ProfileUpdateSerializer,
)
from .services import (
    create_email_verification_otp,
    resend_email_verification_otp,
    verify_email_otp,
)
from .routing import get_backend_dashboard_route, get_dashboard_route


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


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
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
@permission_classes([IsAuthenticated])
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
