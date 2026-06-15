# Create your views here.
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.serializers import UserSerializer

from .models import (
    RevenueShareRule,
    SponsorAccount,
    SponsorAccountMember,
    SponsorBenefit,
    SponsorPackage,
    SponsorWorkflowEvent,
)
from .serializers import (
    AddSponsorMemberSerializer,
    RevenueShareRuleSerializer,
    SponsorAccountCreateSerializer,
    SponsorAccountMemberSerializer,
    SponsorAccountSerializer,
    SponsorBenefitSerializer,
    SponsorPackageSerializer,
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


def is_sponsor_hub_admin(user):
    """
    MVP permission helper for sponsor package management.

    Club admins, league admins, union admins and super admins can create
    packages. Superusers/staff are also allowed.
    """

    if user.is_staff or user.is_superuser:
        return True

    return user.has_role(User.Role.CLUB_ADMIN) or user.has_role(
        User.Role.LEAGUE_ADMIN
    ) or user.has_role(User.Role.UNION_ADMIN) or user.has_role(User.Role.SUPER_ADMIN)


def can_manage_sponsor_package(user, sponsor_package):
    """
    MVP ownership permission for package management.

    Later, this should check the exact club, league, union or platform owner
    once those modules are fully linked by foreign keys.
    """

    if user.is_staff or user.is_superuser or user.has_role(User.Role.SUPER_ADMIN):
        return True

    if sponsor_package.owner_type == "CLUB":
        return user.has_role(User.Role.CLUB_ADMIN)

    if sponsor_package.owner_type == "LEAGUE":
        return user.has_role(User.Role.LEAGUE_ADMIN)

    if sponsor_package.owner_type in ["UNION", "SPORT"]:
        return user.has_role(User.Role.UNION_ADMIN)

    if sponsor_package.owner_type == "PLATFORM":
        return user.has_role(User.Role.SUPER_ADMIN)

    return False


def create_sponsor_package_workflow_event(
    *,
    sponsor_package,
    actor,
    event_type,
    from_status="",
    to_status="",
    note="",
):
    return SponsorWorkflowEvent.objects.create(
        sponsor_package=sponsor_package,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )


def get_sponsor_package_for_request(package_id):
    return (
        SponsorPackage.objects.select_related("created_by", "approved_by")
        .prefetch_related("benefits", "revenue_share_rules")
        .filter(id=package_id)
        .first()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_packages_view(request):
    """
    List sponsor packages or create a sponsor package.

    Non-admin users can only view approved/active packages.
    Sponsor hub admins can view all packages and create packages.
    """

    if request.method == "GET":
        packages = SponsorPackage.objects.select_related(
            "created_by",
            "approved_by",
        ).prefetch_related(
            "benefits",
            "revenue_share_rules",
        )

        if not is_sponsor_hub_admin(request.user):
            packages = packages.filter(
                status__in=[
                    SponsorPackage.Status.APPROVED,
                    SponsorPackage.Status.ACTIVE,
                ]
            )

        owner_type = request.query_params.get("owner_type")
        scope_type = request.query_params.get("scope_type")
        category = request.query_params.get("category")
        status_filter = request.query_params.get("status")

        if owner_type:
            packages = packages.filter(owner_type=owner_type.upper())

        if scope_type:
            packages = packages.filter(scope_type=scope_type.upper())

        if category:
            packages = packages.filter(category=category.upper())

        if status_filter and is_sponsor_hub_admin(request.user):
            packages = packages.filter(status=status_filter.upper())

        return Response(
            {
                "count": packages.count(),
                "results": SponsorPackageSerializer(
                    packages,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if not is_sponsor_hub_admin(request.user):
        return Response(
            {"detail": "You do not have permission to create sponsor packages."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = SponsorPackageSerializer(data=request.data)

    if serializer.is_valid():
        sponsor_package = serializer.save(created_by=request.user)

        create_sponsor_package_workflow_event(
            sponsor_package=sponsor_package,
            actor=request.user,
            event_type=SponsorWorkflowEvent.EventType.PACKAGE_CREATED,
            to_status=sponsor_package.status,
            note="Sponsor package created.",
        )

        return Response(
            {
                "message": "Sponsor package created successfully.",
                "package": SponsorPackageSerializer(
                    sponsor_package,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def sponsor_package_detail_view(request, package_id):
    sponsor_package = get_sponsor_package_for_request(package_id)

    if sponsor_package is None:
        return Response(
            {"detail": "Sponsor package not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        if not is_sponsor_hub_admin(request.user) and sponsor_package.status not in [
            SponsorPackage.Status.APPROVED,
            SponsorPackage.Status.ACTIVE,
        ]:
            return Response(
                {"detail": "You do not have access to this sponsor package."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            SponsorPackageSerializer(
                sponsor_package,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not can_manage_sponsor_package(request.user, sponsor_package):
        return Response(
            {"detail": "You do not have permission to update this sponsor package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = sponsor_package.status

    serializer = SponsorPackageSerializer(
        sponsor_package,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        sponsor_package = serializer.save()

        create_sponsor_package_workflow_event(
            sponsor_package=sponsor_package,
            actor=request.user,
            event_type=SponsorWorkflowEvent.EventType.PACKAGE_SUBMITTED
            if sponsor_package.status == SponsorPackage.Status.SUBMITTED
            and old_status != sponsor_package.status
            else SponsorWorkflowEvent.EventType.PACKAGE_CREATED,
            from_status=old_status,
            to_status=sponsor_package.status,
            note="Sponsor package updated.",
        )

        return Response(
            {
                "message": "Sponsor package updated successfully.",
                "package": SponsorPackageSerializer(
                    sponsor_package,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_package_approve_view(request, package_id):
    sponsor_package = get_sponsor_package_for_request(package_id)

    if sponsor_package is None:
        return Response(
            {"detail": "Sponsor package not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_manage_sponsor_package(request.user, sponsor_package):
        return Response(
            {"detail": "You do not have permission to approve this package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = sponsor_package.status
    sponsor_package.status = SponsorPackage.Status.APPROVED
    sponsor_package.approved_by = request.user
    sponsor_package.approved_at = timezone.now()
    sponsor_package.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )

    create_sponsor_package_workflow_event(
        sponsor_package=sponsor_package,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.PACKAGE_APPROVED,
        from_status=old_status,
        to_status=sponsor_package.status,
        note=request.data.get("note", "Sponsor package approved."),
    )

    return Response(
        {
            "message": "Sponsor package approved successfully.",
            "package": SponsorPackageSerializer(
                sponsor_package,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_package_reject_view(request, package_id):
    sponsor_package = get_sponsor_package_for_request(package_id)

    if sponsor_package is None:
        return Response(
            {"detail": "Sponsor package not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_manage_sponsor_package(request.user, sponsor_package):
        return Response(
            {"detail": "You do not have permission to reject this package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = sponsor_package.status
    sponsor_package.status = SponsorPackage.Status.REJECTED
    sponsor_package.save(update_fields=["status", "updated_at"])

    create_sponsor_package_workflow_event(
        sponsor_package=sponsor_package,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.PACKAGE_REJECTED,
        from_status=old_status,
        to_status=sponsor_package.status,
        note=request.data.get("note", "Sponsor package rejected."),
    )

    return Response(
        {
            "message": "Sponsor package rejected successfully.",
            "package": SponsorPackageSerializer(
                sponsor_package,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_package_benefits_view(request, package_id):
    sponsor_package = get_sponsor_package_for_request(package_id)

    if sponsor_package is None:
        return Response(
            {"detail": "Sponsor package not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        benefits = SponsorBenefit.objects.filter(sponsor_package=sponsor_package)

        return Response(
            {
                "count": benefits.count(),
                "results": SponsorBenefitSerializer(
                    benefits,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if not can_manage_sponsor_package(request.user, sponsor_package):
        return Response(
            {"detail": "You do not have permission to add benefits to this package."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data.copy()
    data["sponsor_package"] = sponsor_package.id

    serializer = SponsorBenefitSerializer(data=data)

    if serializer.is_valid():
        benefit = serializer.save()

        return Response(
            {
                "message": "Sponsor package benefit added successfully.",
                "benefit": SponsorBenefitSerializer(
                    benefit,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_package_revenue_share_rules_view(request, package_id):
    sponsor_package = get_sponsor_package_for_request(package_id)

    if sponsor_package is None:
        return Response(
            {"detail": "Sponsor package not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        rules = RevenueShareRule.objects.filter(sponsor_package=sponsor_package)

        return Response(
            {
                "count": rules.count(),
                "results": RevenueShareRuleSerializer(
                    rules,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if not can_manage_sponsor_package(request.user, sponsor_package):
        return Response(
            {
                "detail": (
                    "You do not have permission to add revenue share rules "
                    "to this package."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data.copy()
    data["sponsor_package"] = sponsor_package.id
    data.pop("agreement", None)

    serializer = RevenueShareRuleSerializer(data=data)

    if serializer.is_valid():
        rule = serializer.save()

        return Response(
            {
                "message": "Revenue share rule added successfully.",
                "revenue_share_rule": RevenueShareRuleSerializer(
                    rule,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
