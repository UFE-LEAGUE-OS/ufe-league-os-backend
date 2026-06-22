# Create your views here.
from decimal import Decimal

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.serializers import UserSerializer

from .models import (
    RevenueDistribution,
    RevenueShareRule,
    SponsorAccount,
    SponsorAgreement,
    SponsorBenefit,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorWorkflowEvent,
)

from .flutterwave import (
    FlutterwaveError,
    flutterwave_is_configured,
    initialize_flutterwave_payment,
    verify_flutterwave_transaction,
)

from .services.payments import (
    confirm_sponsor_payment,
    reject_sponsor_payment,
)

from .services.workflow import (
    create_sponsor_package_workflow_event,
    create_sponsor_workflow_event,
)

from .services.permissions import (
    can_access_sponsor_agreement,
    can_approve_sponsor_agreement,
    can_manage_sponsor_account_finance,
    can_manage_sponsor_agreement,
    can_manage_sponsor_members,
    can_manage_sponsor_package,
    get_user_sponsor_membership,
    is_sponsor_hub_admin,
    package_allows_sponsor_account,
)

from .services.queries import (
    get_pending_payment_schedule_for_agreement,
    get_sponsor_agreement_for_request,
    get_sponsor_package_for_request,
    get_sponsor_payment_for_request,
)

from .services.activation import (
    agreement_can_activate,
    get_activation_blocking_reason,
)

from .services.flutterwave_gateway import (
    confirm_sponsor_payment_from_gateway,
    extract_flutterwave_tx_ref,
    flutterwave_webhook_signature_is_valid,
    make_sponsor_payment_reference,
    mark_flutterwave_payment_failed,
    validate_flutterwave_transaction,
)

from .serializers import (
    AddSponsorMemberSerializer,
    RevenueDistributionSerializer,
    RevenueShareRuleSerializer,
    SponsorAccountCreateSerializer,
    SponsorAccountMemberSerializer,
    SponsorAccountSerializer,
    SponsorAgreementSerializer,
    SponsorBenefitSerializer,
    SponsorPackageSerializer,
    SponsorPaymentScheduleSerializer,
    SponsorPaymentSerializer,
    SponsorRegistrationSerializer,
)


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
            event_type=(
                SponsorWorkflowEvent.EventType.PACKAGE_SUBMITTED
                if sponsor_package.status == SponsorPackage.Status.SUBMITTED
                and old_status != sponsor_package.status
                else SponsorWorkflowEvent.EventType.PACKAGE_CREATED
            ),
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreements_view(request):
    """
    List sponsorship agreements or create a sponsorship agreement.

    Sponsors see agreements for their own sponsor accounts.
    Sponsor hub admins can see all agreements during the MVP.
    """

    if request.method == "GET":
        agreements = SponsorAgreement.objects.select_related(
            "sponsor_account",
            "sponsor_package",
            "created_by",
            "approved_by",
        ).prefetch_related(
            "payment_schedules",
            "payments",
            "revenue_share_rules",
            "revenue_distributions",
            "workflow_events",
        )

        if not is_sponsor_hub_admin(request.user):
            agreements = agreements.filter(
                sponsor_account__members__user=request.user,
                sponsor_account__members__is_active=True,
            ).distinct()

        sponsor_account_id = request.query_params.get("sponsor_account")
        sponsor_package_id = request.query_params.get("sponsor_package")
        status_filter = request.query_params.get("status")
        payment_source = request.query_params.get("payment_source")

        if sponsor_account_id:
            agreements = agreements.filter(sponsor_account_id=sponsor_account_id)

        if sponsor_package_id:
            agreements = agreements.filter(sponsor_package_id=sponsor_package_id)

        if status_filter:
            agreements = agreements.filter(status=status_filter.upper())

        if payment_source:
            agreements = agreements.filter(payment_source=payment_source.upper())

        return Response(
            {
                "count": agreements.count(),
                "results": SponsorAgreementSerializer(
                    agreements,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    sponsor_account = SponsorAccount.objects.filter(
        id=request.data.get("sponsor_account"),
    ).first()

    if sponsor_account is None:
        return Response(
            {"sponsor_account": "Sponsor account not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not can_manage_sponsor_account_finance(request.user, sponsor_account):
        return Response(
            {"detail": "You do not have permission to create this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    sponsor_package = SponsorPackage.objects.filter(
        id=request.data.get("sponsor_package"),
    ).first()

    if sponsor_package is None:
        return Response(
            {"sponsor_package": "Sponsor package not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if sponsor_package.status not in [
        SponsorPackage.Status.APPROVED,
        SponsorPackage.Status.ACTIVE,
    ]:
        return Response(
            {"sponsor_package": "Only approved or active packages can be sponsored."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not package_allows_sponsor_account(sponsor_package, sponsor_account):
        return Response(
            {
                "sponsor_account": (
                    "This sponsor account type is not allowed for this package."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data.copy()
    data.setdefault("total_value", sponsor_package.price_amount)
    data.setdefault("currency", sponsor_package.currency)
    data.setdefault("platform_fee_required", sponsor_package.requires_platform_fee)
    data.setdefault("platform_fee_amount", sponsor_package.platform_fee_amount)

    if sponsor_package.requires_platform_fee:
        data.setdefault(
            "platform_fee_status",
            SponsorAgreement.PlatformFeeStatus.PENDING,
        )

    serializer = SponsorAgreementSerializer(data=data)

    if serializer.is_valid():
        agreement = serializer.save(created_by=request.user)

        create_sponsor_workflow_event(
            sponsor_package=agreement.sponsor_package,
            agreement=agreement,
            actor=request.user,
            event_type=SponsorWorkflowEvent.EventType.AGREEMENT_CREATED,
            to_status=agreement.status,
            note="Sponsorship agreement created.",
        )

        return Response(
            {
                "message": "Sponsorship agreement created successfully.",
                "agreement": SponsorAgreementSerializer(
                    agreement,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_detail_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have access to this sponsorship agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        return Response(
            SponsorAgreementSerializer(
                agreement,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not can_manage_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to update this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = agreement.status
    serializer = SponsorAgreementSerializer(
        agreement,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        agreement = serializer.save()

        event_type = SponsorWorkflowEvent.EventType.AGREEMENT_CREATED
        if (
            agreement.status == SponsorAgreement.Status.SUBMITTED
            and old_status != agreement.status
        ):
            event_type = SponsorWorkflowEvent.EventType.AGREEMENT_SUBMITTED

        create_sponsor_workflow_event(
            sponsor_package=agreement.sponsor_package,
            agreement=agreement,
            actor=request.user,
            event_type=event_type,
            from_status=old_status,
            to_status=agreement.status,
            note="Sponsorship agreement updated.",
        )

        return Response(
            {
                "message": "Sponsorship agreement updated successfully.",
                "agreement": SponsorAgreementSerializer(
                    agreement,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_approve_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to approve this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = agreement.status
    agreement.status = SponsorAgreement.Status.APPROVED
    agreement.approved_by = request.user
    agreement.approved_at = timezone.now()
    agreement.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )

    create_sponsor_workflow_event(
        sponsor_package=agreement.sponsor_package,
        agreement=agreement,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.AGREEMENT_APPROVED,
        from_status=old_status,
        to_status=agreement.status,
        note=request.data.get("note", "Sponsorship agreement approved."),
    )

    return Response(
        {
            "message": "Sponsorship agreement approved successfully.",
            "agreement": SponsorAgreementSerializer(
                agreement,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_reject_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to reject this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_status = agreement.status
    agreement.status = SponsorAgreement.Status.REJECTED
    agreement.save(update_fields=["status", "updated_at"])

    create_sponsor_workflow_event(
        sponsor_package=agreement.sponsor_package,
        agreement=agreement,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.AGREEMENT_REJECTED,
        from_status=old_status,
        to_status=agreement.status,
        note=request.data.get("note", "Sponsorship agreement rejected."),
    )

    return Response(
        {
            "message": "Sponsorship agreement rejected successfully.",
            "agreement": SponsorAgreementSerializer(
                agreement,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_activate_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to activate this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if agreement.status == SponsorAgreement.Status.ACTIVE:
        return Response(
            {"detail": "This sponsorship agreement is already active."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if agreement.status not in [
        SponsorAgreement.Status.APPROVED,
        SponsorAgreement.Status.PENDING_PAYMENT,
    ]:
        return Response(
            {"detail": "Only approved or pending payment agreements can be activated."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    blocking_reason = get_activation_blocking_reason(agreement)
    if blocking_reason or not agreement_can_activate(agreement):
        return Response(
            {
                "detail": (
                    blocking_reason or "Agreement activation requirements are not met."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    old_status = agreement.status
    agreement.status = SponsorAgreement.Status.ACTIVE
    agreement.platform_activation_allowed = True
    agreement.save(
        update_fields=[
            "status",
            "platform_activation_allowed",
            "updated_at",
        ]
    )

    create_sponsor_workflow_event(
        sponsor_package=agreement.sponsor_package,
        agreement=agreement,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.AGREEMENT_ACTIVATED,
        from_status=old_status,
        to_status=agreement.status,
        note=request.data.get("note", "Sponsorship agreement activated."),
    )

    return Response(
        {
            "message": "Sponsorship agreement activated successfully.",
            "agreement": SponsorAgreementSerializer(
                agreement,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_payment_schedules_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have access to this sponsorship agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        schedules = SponsorPaymentSchedule.objects.filter(agreement=agreement)

        return Response(
            {
                "count": schedules.count(),
                "results": SponsorPaymentScheduleSerializer(
                    schedules,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to add payment schedules."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data.copy()
    data["agreement"] = agreement.id
    serializer = SponsorPaymentScheduleSerializer(data=data)

    if serializer.is_valid():
        payment_schedule = serializer.save()

        return Response(
            {
                "message": "Sponsor payment schedule created successfully.",
                "payment_schedule": SponsorPaymentScheduleSerializer(
                    payment_schedule,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_payments_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have access to this sponsorship agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        payments = SponsorPayment.objects.filter(agreement=agreement)

        return Response(
            {
                "count": payments.count(),
                "results": SponsorPaymentSerializer(
                    payments,
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    if not can_manage_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to record this payment."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data.copy()
    data["agreement"] = agreement.id
    serializer = SponsorPaymentSerializer(data=data)

    if serializer.is_valid():
        payment_schedule = serializer.validated_data.get("payment_schedule")
        if payment_schedule and payment_schedule.agreement_id != agreement.id:
            return Response(
                {
                    "payment_schedule": (
                        "Payment schedule does not belong to this agreement."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = serializer.save(recorded_by=request.user)

        create_sponsor_workflow_event(
            sponsor_package=agreement.sponsor_package,
            agreement=agreement,
            payment=payment,
            actor=request.user,
            event_type=SponsorWorkflowEvent.EventType.PAYMENT_REGISTERED,
            to_status=payment.status,
            note="Sponsor payment recorded.",
        )

        return Response(
            {
                "message": "Sponsor payment recorded successfully.",
                "payment": SponsorPaymentSerializer(
                    payment,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_payment_confirm_view(request, payment_id):
    payment = get_sponsor_payment_for_request(payment_id)

    if payment is None:
        return Response(
            {"detail": "Sponsor payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    agreement = payment.agreement

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to confirm this payment."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if payment.status != SponsorPayment.Status.PENDING:
        return Response(
            {"detail": "Only pending payments can be confirmed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment, distributions = confirm_sponsor_payment(
        payment,
        actor=request.user,
        note=request.data.get("note", "Sponsor payment confirmed."),
        activation_note="Agreement activated after payment confirmation.",
    )

    return Response(
        {
            "message": "Sponsor payment confirmed successfully.",
            "payment": SponsorPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            "revenue_distributions": RevenueDistributionSerializer(
                distributions,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_payment_reject_view(request, payment_id):
    payment = get_sponsor_payment_for_request(payment_id)

    if payment is None:
        return Response(
            {"detail": "Sponsor payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    agreement = payment.agreement

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to reject this payment."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if payment.status != SponsorPayment.Status.PENDING:
        return Response(
            {"detail": "Only pending payments can be rejected."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = reject_sponsor_payment(
        payment,
        actor=request.user,
        note=request.data.get("note", "Sponsor payment rejected."),
    )

    return Response(
        {
            "message": "Sponsor payment rejected successfully.",
            "payment": SponsorPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_revenue_share_rules_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have access to this sponsorship agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        rules = RevenueShareRule.objects.filter(agreement=agreement)

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

    if not can_approve_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to add agreement revenue rules."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data.copy()
    data["agreement"] = agreement.id
    data.pop("sponsor_package", None)
    serializer = RevenueShareRuleSerializer(data=data)

    if serializer.is_valid():
        rule = serializer.save()

        return Response(
            {
                "message": "Agreement revenue share rule added successfully.",
                "revenue_share_rule": RevenueShareRuleSerializer(
                    rule,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_revenue_distributions_view(request, agreement_id):
    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have access to this sponsorship agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    distributions = RevenueDistribution.objects.filter(agreement=agreement)

    return Response(
        {
            "count": distributions.count(),
            "results": RevenueDistributionSerializer(
                distributions,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sponsor_payment_revenue_distributions_view(request, payment_id):
    payment = get_sponsor_payment_for_request(payment_id)

    if payment is None:
        return Response(
            {"detail": "Sponsor payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_access_sponsor_agreement(request.user, payment.agreement):
        return Response(
            {"detail": "You do not have access to this sponsor payment."},
            status=status.HTTP_403_FORBIDDEN,
        )

    distributions = RevenueDistribution.objects.filter(payment=payment)

    return Response(
        {
            "count": distributions.count(),
            "results": RevenueDistributionSerializer(
                distributions,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sponsor_agreement_flutterwave_initialize_view(request, agreement_id):
    """
    Create a pending SponsorPayment and ask Flutterwave for a checkout link.
    """

    agreement = get_sponsor_agreement_for_request(agreement_id)

    if agreement is None:
        return Response(
            {"detail": "Sponsorship agreement not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not can_manage_sponsor_agreement(request.user, agreement):
        return Response(
            {"detail": "You do not have permission to pay for this agreement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not flutterwave_is_configured():
        return Response(
            {"detail": "Flutterwave is not configured for this environment."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if agreement.payment_source != SponsorAgreement.PaymentSource.PLATFORM:
        return Response(
            {"detail": "Only platform-paid agreements can use Flutterwave checkout."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if agreement.status not in [
        SponsorAgreement.Status.APPROVED,
        SponsorAgreement.Status.PENDING_PAYMENT,
    ]:
        return Response(
            {"detail": "Only approved or pending payment agreements can be paid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment_schedule = get_pending_payment_schedule_for_agreement(
        agreement,
        request.data.get("payment_schedule"),
    )

    amount = request.data.get("amount_paid") or agreement.total_value
    if payment_schedule is not None:
        amount = request.data.get("amount_paid") or payment_schedule.amount_due

    amount = Decimal(str(amount))
    if amount <= 0:
        return Response(
            {"amount_paid": "Payment amount must be greater than zero."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = SponsorPayment.objects.create(
        agreement=agreement,
        payment_schedule=payment_schedule,
        amount_paid=amount,
        currency=agreement.currency,
        payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
        provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
        transaction_reference=make_sponsor_payment_reference(agreement),
        recorded_by=request.user,
    )

    try:
        flutterwave_response = initialize_flutterwave_payment(payment, request=request)
    except FlutterwaveError as exc:
        payment.provider_status = "INITIALIZATION_FAILED"
        payment.provider_response = {"error": str(exc)}
        payment.save(update_fields=["provider_status", "provider_response"])

        return Response(
            {
                "detail": "Could not initialize Flutterwave payment.",
                "error": str(exc),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    checkout_url = flutterwave_response.get("data", {}).get("link", "")

    payment.checkout_url = checkout_url
    payment.checkout_initialized_at = timezone.now()
    payment.provider_status = flutterwave_response.get("status", "")
    payment.provider_response = flutterwave_response
    payment.save(
        update_fields=[
            "checkout_url",
            "checkout_initialized_at",
            "provider_status",
            "provider_response",
        ]
    )

    create_sponsor_workflow_event(
        sponsor_package=agreement.sponsor_package,
        agreement=agreement,
        payment=payment,
        actor=request.user,
        event_type=SponsorWorkflowEvent.EventType.PAYMENT_REGISTERED,
        to_status=payment.status,
        note="Flutterwave checkout initialized.",
    )

    return Response(
        {
            "message": "Flutterwave payment initialized successfully.",
            "checkout_url": checkout_url,
            "tx_ref": payment.transaction_reference,
            "payment": SponsorPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def flutterwave_verify_view(request):
    """
    Verify payment after Flutterwave redirects the user back to League OS.

    This endpoint is public because Flutterwave redirects to it.
    It does not trust the redirect alone. It verifies with Flutterwave first.
    """

    tx_ref = request.query_params.get("tx_ref")

    if not tx_ref:
        return Response(
            {"tx_ref": "Transaction reference is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = SponsorPayment.objects.filter(
        transaction_reference=tx_ref,
        provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
    ).first()

    if payment is None:
        return Response(
            {"detail": "Sponsor payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        flutterwave_response = verify_flutterwave_transaction(tx_ref)
    except FlutterwaveError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    is_valid, error_message = validate_flutterwave_transaction(
        payment,
        flutterwave_response,
    )

    if not is_valid:
        status_value = flutterwave_response.get("data", {}).get("status", "failed")
        mark_flutterwave_payment_failed(payment, flutterwave_response, status_value)

        return Response(
            {
                "detail": error_message,
                "payment": SponsorPaymentSerializer(
                    payment,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment, distributions = confirm_sponsor_payment_from_gateway(
        payment,
        flutterwave_response,
    )

    return Response(
        {
            "message": "Flutterwave payment verified successfully.",
            "payment": SponsorPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            "revenue_distributions": RevenueDistributionSerializer(
                distributions,
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@csrf_exempt
@api_view(["POST"])
def flutterwave_webhook_view(request):
    """
    Receive Flutterwave webhook events.

    Webhooks are server-to-server notifications. They are important because
    users can close the browser before redirecting back to your app.
    """

    if not flutterwave_webhook_signature_is_valid(request):
        return Response(
            {"detail": "Invalid Flutterwave webhook signature."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    tx_ref = extract_flutterwave_tx_ref(request.data)

    if not tx_ref:
        return Response(
            {"tx_ref": "Transaction reference is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment = SponsorPayment.objects.filter(
        transaction_reference=tx_ref,
        provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
    ).first()

    if payment is None:
        return Response(
            {"detail": "Sponsor payment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        flutterwave_response = verify_flutterwave_transaction(tx_ref)
    except FlutterwaveError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    is_valid, error_message = validate_flutterwave_transaction(
        payment,
        flutterwave_response,
    )

    if not is_valid:
        status_value = flutterwave_response.get("data", {}).get("status", "failed")
        mark_flutterwave_payment_failed(payment, flutterwave_response, status_value)

        return Response(
            {"detail": error_message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment, distributions = confirm_sponsor_payment_from_gateway(
        payment,
        flutterwave_response,
    )

    return Response(
        {
            "message": "Flutterwave webhook processed successfully.",
            "payment": SponsorPaymentSerializer(payment).data,
            "revenue_distributions": RevenueDistributionSerializer(
                distributions,
                many=True,
            ).data,
        },
        status=status.HTTP_200_OK,
    )
