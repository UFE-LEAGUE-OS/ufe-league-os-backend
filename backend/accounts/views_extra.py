from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit, IsSuperAdmin
from accounts.models import Club, User
from accounts.rbac import log_role_change
from accounts.serializers import (
    AdminCreateUserSerializer,
    BecomeSponsorSerializer,
    UserSerializer,
)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit, IsSuperAdmin])
def superadmin_create_user_view(request):
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


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def become_sponsor_view(request):
    serializer = BecomeSponsorSerializer(data=request.data)

    if serializer.is_valid():
        user = request.user
        user.is_sponsor = True
        user.sponsor_type = serializer.validated_data["sponsor_type"]
        user.save(update_fields=["is_sponsor", "sponsor_type"])

        return Response(
            {
                "message": "You are now a sponsor.",
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
