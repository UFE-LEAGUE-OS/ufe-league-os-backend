# Create your views here.
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.serializers import UserSerializer

from .models import SponsorAccount, SponsorAccountMember
from .serializers import (
    AddSponsorMemberSerializer,
    SponsorAccountCreateSerializer,
    SponsorAccountMemberSerializer,
    SponsorAccountSerializer,
    SponsorRegistrationSerializer,
)


def get_user_sponsor_membership(user, sponsor_account):
    return SponsorAccountMember.objects.filter(
        sponsor_account=sponsor_account,
        user=user,
        is_active=True,
    ).first()


def can_manage_sponsor_members(user, sponsor_account):
    membership = get_user_sponsor_membership(user, sponsor_account)

    if membership is None:
        return False

    return membership.member_role in [
        SponsorAccountMember.MemberRole.OWNER,
        SponsorAccountMember.MemberRole.ADMIN,
    ]


@api_view(["POST"])
def sponsor_register_view(request):
    """
    Register a new user directly as an individual or corporate sponsor.
    """

    serializer = SponsorRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        sponsor_account = serializer.save()
        user = sponsor_account.owner

        return Response(
            {
                "message": (
                    "Sponsor registration successful. Please verify your email "
                    "address using the OTP sent to your email."
                ),
                "requires_email_verification": not user.is_email_verified,
                "user": UserSerializer(user, context={"request": request}).data,
                "sponsor_account": SponsorAccountSerializer(
                    sponsor_account,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_accounts_view(request):
    """
    List sponsor accounts for the logged-in user or create one.
    """

    if request.method == "GET":
        sponsor_accounts = SponsorAccount.objects.filter(
            members__user=request.user,
            members__is_active=True,
        ).distinct()

        return Response(
            {
                "count": sponsor_accounts.count(),
                "results": SponsorAccountSerializer(
                    sponsor_accounts,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    serializer = SponsorAccountCreateSerializer(
        data=request.data,
        context={"request": request},
    )

    if serializer.is_valid():
        sponsor_account = serializer.save()

        return Response(
            {
                "message": "Sponsor account created successfully.",
                "sponsor_account": SponsorAccountSerializer(
                    sponsor_account,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sponsor_account_detail_view(request, account_id):
    sponsor_account = SponsorAccount.objects.filter(id=account_id).first()

    if sponsor_account is None:
        return Response(
            {"detail": "Sponsor account not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if get_user_sponsor_membership(request.user, sponsor_account) is None:
        return Response(
            {"detail": "You do not have access to this sponsor account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        SponsorAccountSerializer(
            sponsor_account,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_account_members_view(request, account_id):
    sponsor_account = SponsorAccount.objects.filter(id=account_id).first()

    if sponsor_account is None:
        return Response(
            {"detail": "Sponsor account not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if get_user_sponsor_membership(request.user, sponsor_account) is None:
        return Response(
            {"detail": "You do not have access to this sponsor account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        members = sponsor_account.members.select_related("user").filter(is_active=True)

        return Response(
            {
                "count": members.count(),
                "results": SponsorAccountMemberSerializer(
                    members,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if sponsor_account.sponsor_type != SponsorAccount.SponsorType.CORPORATE:
        return Response(
            {"detail": "Only corporate sponsor accounts can add additional members."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not can_manage_sponsor_members(request.user, sponsor_account):
        return Response(
            {"detail": "You do not have permission to add sponsor members."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AddSponsorMemberSerializer(
        data=request.data,
        context={"sponsor_account": sponsor_account},
    )

    if serializer.is_valid():
        member = serializer.save()

        return Response(
            {
                "message": "Sponsor member added successfully.",
                "member": SponsorAccountMemberSerializer(
                    member,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
