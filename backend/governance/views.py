from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin
from accounts.rbac import log_role_change

from .models import CompetitionFormat, LeagueStandard, Rule, SportVariant
from .serializers import (
    CompetitionFormatListSerializer,
    CompetitionFormatSerializer,
    LeagueStandardSerializer,
    PublishStandardsSerializer,
    RuleListSerializer,
    RuleSerializer,
    SportVariantListSerializer,
    SportVariantSerializer,
)


# ---------------------------------------------------------------------------
# SPORT VARIANTS CRUD
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def sport_variant_list_create_view(request):
    """
    GET: List all sport variants (super admin only).
    POST: Create a new sport variant.
    """
    if request.method == "GET":
        queryset = SportVariant.objects.all().order_by("name")
        serializer = SportVariantListSerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = SportVariantSerializer(data=request.data)
    if serializer.is_valid():
        variant = serializer.save()
        log_role_change(
            target_user=request.user,
            previous_role=None,
            new_role=None,
            actor=request.user,
            reason=f"Created sport variant: {variant.name}",
        )
        return Response(
            SportVariantSerializer(variant).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def sport_variant_detail_view(request, pk):
    """
    GET: Retrieve a sport variant.
    PUT/PATCH: Update a sport variant.
    DELETE: Delete a sport variant.
    """
    try:
        variant = SportVariant.objects.get(pk=pk)
    except SportVariant.DoesNotExist:
        return Response(
            {"detail": "Sport variant not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = SportVariantSerializer(variant)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = SportVariantSerializer(variant, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            log_role_change(
                target_user=request.user,
                previous_role=None,
                new_role=None,
                actor=request.user,
                reason=f"Updated sport variant: {updated.name}",
            )
            return Response(SportVariantSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    name = variant.name
    variant.delete()
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Deleted sport variant: {name}",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def sport_variant_verify_view(request, pk):
    """
    POST: Mark a sport variant as verified by a super admin.
    """
    try:
        variant = SportVariant.objects.get(pk=pk)
    except SportVariant.DoesNotExist:
        return Response(
            {"detail": "Sport variant not found."}, status=status.HTTP_404_NOT_FOUND
        )

    variant.is_verified = True
    variant.save(update_fields=["is_verified"])
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Verified sport variant: {variant.name}",
    )
    return Response(
        {
            "detail": f"Sport variant '{variant.name}' verified successfully.",
            "variant": SportVariantSerializer(variant).data,
        }
    )


# ---------------------------------------------------------------------------
# COMPETITION FORMATS CRUD
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def competition_format_list_create_view(request):
    """
    GET: List all competition formats.
    POST: Create a new competition format.
    """
    if request.method == "GET":
        queryset = CompetitionFormat.objects.all().order_by("name")
        serializer = CompetitionFormatListSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = CompetitionFormatSerializer(data=request.data)
    if serializer.is_valid():
        fmt = serializer.save()
        log_role_change(
            target_user=request.user,
            previous_role=None,
            new_role=None,
            actor=request.user,
            reason=f"Created competition format: {fmt.name}",
        )
        return Response(
            CompetitionFormatSerializer(fmt).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def competition_format_detail_view(request, pk):
    """
    GET: Retrieve a competition format.
    PUT/PATCH: Update a competition format.
    DELETE: Delete a competition format.
    """
    try:
        fmt = CompetitionFormat.objects.get(pk=pk)
    except CompetitionFormat.DoesNotExist:
        return Response(
            {"detail": "Competition format not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = CompetitionFormatSerializer(fmt)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = CompetitionFormatSerializer(
            fmt, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            log_role_change(
                target_user=request.user,
                previous_role=None,
                new_role=None,
                actor=request.user,
                reason=f"Updated competition format: {updated.name}",
            )
            return Response(CompetitionFormatSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    name = fmt.name
    fmt.delete()
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Deleted competition format: {name}",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def competition_format_verify_view(request, pk):
    """
    POST: Mark a competition format as verified by a super admin.
    """
    try:
        fmt = CompetitionFormat.objects.get(pk=pk)
    except CompetitionFormat.DoesNotExist:
        return Response(
            {"detail": "Competition format not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    fmt.is_verified = True
    fmt.save(update_fields=["is_verified"])
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Verified competition format: {fmt.name}",
    )
    return Response(
        {
            "detail": f"Competition format '{fmt.name}' verified successfully.",
            "format": CompetitionFormatSerializer(fmt).data,
        }
    )


# ---------------------------------------------------------------------------
# RULES & STANDARDS CRUD
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def rule_list_create_view(request):
    """
    GET: List all rules & standards.
    POST: Create a new rule/standard.
    """
    if request.method == "GET":
        queryset = Rule.objects.all().order_by("category", "title")
        serializer = RuleListSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = RuleSerializer(data=request.data)
    if serializer.is_valid():
        rule = serializer.save(created_by=request.user)
        log_role_change(
            target_user=request.user,
            previous_role=None,
            new_role=None,
            actor=request.user,
            reason=f"Created rule: {rule.title} v{rule.version}",
        )
        return Response(RuleSerializer(rule).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def rule_detail_view(request, pk):
    """
    GET: Retrieve a rule/standard.
    PUT/PATCH: Update a rule/standard.
    DELETE: Delete a rule/standard.
    """
    try:
        rule = Rule.objects.get(pk=pk)
    except Rule.DoesNotExist:
        return Response({"detail": "Rule not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = RuleSerializer(rule)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = RuleSerializer(rule, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            log_role_change(
                target_user=request.user,
                previous_role=None,
                new_role=None,
                actor=request.user,
                reason=f"Updated rule: {updated.title} v{updated.version}",
            )
            return Response(RuleSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    title = rule.title
    rule.delete()
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Deleted rule: {title}",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def rule_publish_view(request, pk):
    """
    POST: Publish a rule/standard so it becomes available for league assignment.
    """
    try:
        rule = Rule.objects.get(pk=pk)
    except Rule.DoesNotExist:
        return Response({"detail": "Rule not found."}, status=status.HTTP_404_NOT_FOUND)

    if rule.is_published:
        return Response(
            {"detail": f"Rule '{rule.title}' is already published."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rule.is_published = True
    rule.published_at = timezone.now()
    rule.save(update_fields=["is_published", "published_at"])
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Published rule: {rule.title} v{rule.version}",
    )
    return Response(
        {
            "detail": f"Rule '{rule.title}' published successfully.",
            "rule": RuleSerializer(rule).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def rule_unpublish_view(request, pk):
    """
    POST: Unpublish a rule, removing it from league availability.
    """
    try:
        rule = Rule.objects.get(pk=pk)
    except Rule.DoesNotExist:
        return Response({"detail": "Rule not found."}, status=status.HTTP_404_NOT_FOUND)

    if not rule.is_published:
        return Response(
            {"detail": f"Rule '{rule.title}' is not currently published."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rule.is_published = False
    rule.published_at = None
    rule.save(update_fields=["is_published", "published_at"])
    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Unpublished rule: {rule.title} v{rule.version}",
    )
    return Response({"detail": f"Rule '{rule.title}' unpublished successfully."})


# ---------------------------------------------------------------------------
# PUBLISH STANDARDS TO LEAGUES API
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def league_standard_list_create_view(request):
    """
    GET: List all league standard assignments.
    POST: Publish one or more rules to one or more leagues.
    """
    if request.method == "GET":
        queryset = (
            LeagueStandard.objects.all()
            .select_related("rule", "league", "assigned_by", "accepted_by")
            .order_by("-assigned_at")
        )
        serializer = LeagueStandardSerializer(queryset, many=True)
        return Response(serializer.data)

    # POST - Publish standards
    serializer = PublishStandardsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    rule_ids = serializer.validated_data["rule_ids"]
    league_ids = serializer.validated_data["league_ids"]
    notes = serializer.validated_data.get("notes", "")

    # Ensure rules are published
    unpublished = Rule.objects.filter(id__in=rule_ids, is_published=False).values_list(
        "title", flat=True
    )
    if unpublished:
        return Response(
            {
                "detail": (
                    f"The following rules must be published first before "
                    f"assigning to leagues: {', '.join(unpublished)}"
                ),
                "unpublished_rules": list(unpublished),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    created = []
    already_exist = []

    for rule_id in rule_ids:
        for league_id in league_ids:
            obj, was_created = LeagueStandard.objects.get_or_create(
                rule_id=rule_id,
                league_id=league_id,
                defaults={
                    "assigned_by": request.user,
                    "notes": notes,
                },
            )
            if was_created:
                created.append({"rule_id": rule_id, "league_id": league_id})
            else:
                already_exist.append({"rule_id": rule_id, "league_id": league_id})

    log_role_change(
        target_user=request.user,
        previous_role=None,
        new_role=None,
        actor=request.user,
        reason=f"Published {len(created)} standard(s) to leagues",
    )

    return Response(
        {
            "detail": f"{len(created)} standard(s) assigned successfully.",
            "created": created,
            "already_exist": already_exist,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsSuperAdmin])
def league_standard_remove_view(request, pk):
    """
    DELETE: Remove a league standard assignment.
    """
    try:
        assignment = LeagueStandard.objects.get(pk=pk)
    except LeagueStandard.DoesNotExist:
        return Response(
            {"detail": "League standard assignment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    assignment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def league_standards_by_league_view(request, league_pk):
    """
    GET: List all standards assigned to a specific league.
    """
    queryset = (
        LeagueStandard.objects.filter(league_id=league_pk)
        .select_related("rule", "league", "assigned_by", "accepted_by")
        .order_by("-assigned_at")
    )
    serializer = LeagueStandardSerializer(queryset, many=True)
    return Response(serializer.data)
