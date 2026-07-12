from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAuthenticatedAudit
from accounts.rbac import log_governance_action

from .management_serializers import (
    FixtureOfficialAssignmentManagementSerializer,
    LeagueAdminScopeSerializer,
    UnionMatchOfficialManagementSerializer,
)
from .models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueAdminScope,
    Match,
    UnionMatchOfficial,
)
from .serializers import MatchListSerializer
from .union_management_views import _require_permission, _resolve_membership


MANAGER_SCOPE_ROLES = {
    LeagueAdminScope.Role.LEAGUE_ADMIN,
    LeagueAdminScope.Role.COMPETITION_ADMIN,
    LeagueAdminScope.Role.OFFICIALS_COORDINATOR,
}
ADMIN_ASSIGNMENT_STATUSES = {
    FixtureOfficialAssignment.Status.PROPOSED,
    FixtureOfficialAssignment.Status.ASSIGNED,
    FixtureOfficialAssignment.Status.CANCELLED,
}
OFFICIAL_RESPONSE_STATUSES = {
    FixtureOfficialAssignment.Status.ACCEPTED,
    FixtureOfficialAssignment.Status.DECLINED,
}


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=status_code)


def _parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_super_admin(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == User.Role.SUPER_ADMIN
    )


def _active_scopes(user, manage_only=False):
    scopes = LeagueAdminScope.objects.filter(user=user, is_active=True).select_related(
        "league",
        "league__union",
        "competition",
    )
    if manage_only:
        scopes = scopes.filter(role__in=MANAGER_SCOPE_ROLES)
    return scopes


def _scope_filter(scopes):
    query = models.Q(pk__in=[])
    for scope in scopes:
        if scope.competition_id:
            query |= models.Q(match__competition_id=scope.competition_id)
        else:
            query |= models.Q(match__competition__league_id=scope.league_id)
    return query


def _match_scope_filter(scopes):
    query = models.Q(pk__in=[])
    for scope in scopes:
        if scope.competition_id:
            query |= models.Q(competition_id=scope.competition_id)
        else:
            query |= models.Q(competition__league_id=scope.league_id)
    return query


def _user_can_manage_match(user, match):
    if _is_super_admin(user):
        return True

    return _active_scopes(user, manage_only=True).filter(
        models.Q(
            league_id=match.competition.league_id,
            competition__isnull=True,
        )
        | models.Q(competition_id=match.competition_id)
    ).exists()


def _user_can_view_league(user, league_id):
    if _is_super_admin(user):
        return True
    return _active_scopes(user).filter(league_id=league_id).exists()


def _assignment_queryset():
    return FixtureOfficialAssignment.objects.select_related(
        "match",
        "match__competition",
        "match__competition__league",
        "match__competition__league__union",
        "match__home_club",
        "match__away_club",
        "official",
        "official__user",
        "assigned_by",
    )


def _normalise_role_type(value):
    role = str(value or "").strip().upper()
    valid = {choice[0] for choice in UnionMatchOfficial.RoleType.choices}
    return role if role in valid else None


def _admin_status(value, default=FixtureOfficialAssignment.Status.ASSIGNED):
    value = str(value or default).strip().upper()
    return value if value in ADMIN_ASSIGNMENT_STATUSES else None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_admin_scopes_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user,
        workspace,
        "union.users.manage",
    )
    if permission_error:
        return permission_error

    scopes = LeagueAdminScope.objects.filter(
        league__union=workspace.related_union,
    ).select_related(
        "user",
        "league",
        "league__union",
        "competition",
    )

    if request.method == "GET":
        league_value = request.query_params.get("league")
        competition_value = request.query_params.get("competition")
        if league_value:
            scopes = scopes.filter(league_id=league_value)
        if competition_value:
            scopes = scopes.filter(competition_id=competition_value)
        return Response(
            {
                "count": scopes.count(),
                "results": LeagueAdminScopeSerializer(scopes, many=True).data,
            }
        )

    user_value = request.data.get("user") or request.data.get("email")
    user = None
    if str(user_value or "").isdigit():
        user = get_user_model().objects.filter(id=user_value).first()
    elif user_value:
        user = get_user_model().objects.filter(
            email__iexact=str(user_value).strip()
        ).first()
    if user is None:
        return _error("Select an existing user for this administration scope.")

    league = League.objects.filter(
        id=request.data.get("league"),
        union=workspace.related_union,
    ).first()
    if league is None:
        return _error("Select a league belonging to this union workspace.")

    competition = None
    competition_value = request.data.get("competition")
    if competition_value not in (None, ""):
        competition = Competition.objects.filter(
            id=competition_value,
            league=league,
        ).first()
        if competition is None:
            return _error("Select a competition belonging to the selected league.")

    scope_role = str(
        request.data.get("role") or LeagueAdminScope.Role.LEAGUE_ADMIN
    ).strip().upper()
    valid_roles = {choice[0] for choice in LeagueAdminScope.Role.choices}
    if scope_role not in valid_roles:
        return _error("Select a valid league administration role.")

    lookup = {
        "user": user,
        "league": league,
        "competition": competition,
    }
    scope, created = LeagueAdminScope.objects.update_or_create(
        **lookup,
        defaults={
            "role": scope_role,
            "is_active": _parse_bool(request.data.get("is_active"), True),
            "created_by": request.user,
        },
    )

    log_governance_action(
        actor=request.user,
        target_user=user,
        action=(
            "league_admin_scope_created"
            if created
            else "league_admin_scope_updated"
        ),
        details={
            "workspace": workspace.slug,
            "scope": scope.id,
            "league": league.id,
            "competition": competition.id if competition else None,
            "role": scope.role,
            "is_active": scope.is_active,
        },
    )

    return Response(
        LeagueAdminScopeSerializer(scope).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_admin_scope_detail_view(request, scope_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user,
        workspace,
        "union.users.manage",
    )
    if permission_error:
        return permission_error

    scope = (
        LeagueAdminScope.objects.select_related(
            "user",
            "league",
            "league__union",
            "competition",
        )
        .filter(id=scope_id, league__union=workspace.related_union)
        .first()
    )
    if scope is None:
        return _error("League administration scope not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(LeagueAdminScopeSerializer(scope).data)

    if request.method == "DELETE":
        details = {
            "workspace": workspace.slug,
            "scope": scope.id,
            "league": scope.league_id,
            "competition": scope.competition_id,
        }
        target_user = scope.user
        scope.delete()
        log_governance_action(
            actor=request.user,
            target_user=target_user,
            action="league_admin_scope_deleted",
            details=details,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "role" in request.data:
        scope_role = str(request.data.get("role") or "").strip().upper()
        valid_roles = {choice[0] for choice in LeagueAdminScope.Role.choices}
        if scope_role not in valid_roles:
            return _error("Select a valid league administration role.")
        scope.role = scope_role
    if "is_active" in request.data:
        scope.is_active = _parse_bool(request.data.get("is_active"), scope.is_active)
    scope.save()

    log_governance_action(
        actor=request.user,
        target_user=scope.user,
        action="league_admin_scope_updated",
        details={
            "workspace": workspace.slug,
            "scope": scope.id,
            "league": scope.league_id,
            "competition": scope.competition_id,
            "role": scope.role,
            "is_active": scope.is_active,
        },
    )
    return Response(LeagueAdminScopeSerializer(scope).data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_scopes_view(request):
    scopes = _active_scopes(request.user)
    if not scopes.exists() and not _is_super_admin(request.user):
        return _error(
            "No active league or competition administration scope was found.",
            status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            "count": scopes.count(),
            "results": LeagueAdminScopeSerializer(scopes, many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_fixtures_view(request):
    fixtures = Match.objects.select_related(
        "competition",
        "competition__league",
        "home_club",
        "away_club",
    )

    if not _is_super_admin(request.user):
        scopes = list(_active_scopes(request.user))
        if not scopes:
            return _error(
                "No active league or competition administration scope was found.",
                status.HTTP_403_FORBIDDEN,
            )
        fixtures = fixtures.filter(_match_scope_filter(scopes))

    league_value = request.query_params.get("league")
    competition_value = request.query_params.get("competition")
    if league_value:
        fixtures = fixtures.filter(competition__league_id=league_value)
    if competition_value:
        fixtures = fixtures.filter(competition_id=competition_value)

    status_value = request.query_params.get("status")
    if status_value:
        fixtures = fixtures.filter(status=str(status_value).upper())
    else:
        fixtures = fixtures.filter(
            status__in=[Match.Status.SCHEDULED, Match.Status.POSTPONED]
        )

    return Response(
        {
            "count": fixtures.count(),
            "results": MatchListSerializer(
                fixtures.order_by("match_date"),
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_match_officials_view(request):
    league_value = request.query_params.get("league")
    competition_value = request.query_params.get("competition")

    league = None
    if competition_value:
        competition = Competition.objects.select_related("league", "league__union").filter(
            id=competition_value
        ).first()
        if competition is None:
            return _error("Competition not found.", status.HTTP_404_NOT_FOUND)
        if not _user_can_view_league(request.user, competition.league_id):
            return _error("You cannot access this competition.", status.HTTP_403_FORBIDDEN)
        if not _is_super_admin(request.user):
            has_competition_access = _active_scopes(request.user).filter(
                models.Q(
                    league_id=competition.league_id,
                    competition__isnull=True,
                )
                | models.Q(competition_id=competition.id)
            ).exists()
            if not has_competition_access:
                return _error("You cannot access this competition.", status.HTTP_403_FORBIDDEN)
        league = competition.league
    elif league_value:
        league = League.objects.select_related("union").filter(id=league_value).first()
        if league is None:
            return _error("League not found.", status.HTTP_404_NOT_FOUND)
        if not _user_can_view_league(request.user, league.id):
            return _error("You cannot access this league.", status.HTTP_403_FORBIDDEN)

    if league is not None:
        officials = UnionMatchOfficial.objects.filter(
            union=league.union,
            status=UnionMatchOfficial.Status.AVAILABLE,
        )
    elif _is_super_admin(request.user):
        officials = UnionMatchOfficial.objects.filter(
            status=UnionMatchOfficial.Status.AVAILABLE
        )
    else:
        union_ids = _active_scopes(request.user).values_list(
            "league__union_id", flat=True
        )
        officials = UnionMatchOfficial.objects.filter(
            union_id__in=union_ids,
            status=UnionMatchOfficial.Status.AVAILABLE,
        )

    query = str(request.query_params.get("q") or "").strip()
    if query:
        officials = officials.filter(
            models.Q(full_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(role_type__icontains=query)
            | models.Q(certification_level__icontains=query)
        )

    officials = officials.select_related("user", "union").distinct().order_by(
        "full_name"
    )
    labels = dict(UnionMatchOfficial.RoleType.choices)

    return Response(
        {
            "count": officials.count(),
            "role_options": [
                {"value": value, "label": label}
                for value, label in labels.items()
            ],
            "results": UnionMatchOfficialManagementSerializer(
                officials,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_appointments_view(request):
    if request.method == "GET":
        assignments = _assignment_queryset()

        if not _is_super_admin(request.user):
            scopes = list(_active_scopes(request.user))
            if not scopes:
                return _error(
                    "No active league or competition administration scope was found.",
                    status.HTTP_403_FORBIDDEN,
                )
            assignments = assignments.filter(_scope_filter(scopes))

        filters = {
            "match__competition__league_id": request.query_params.get("league"),
            "match__competition_id": request.query_params.get("competition"),
            "match_id": request.query_params.get("match"),
            "official_id": request.query_params.get("official"),
            "status": request.query_params.get("status"),
        }
        for field, value in filters.items():
            if value:
                assignments = assignments.filter(**{field: value})

        return Response(
            {
                "count": assignments.count(),
                "results": FixtureOfficialAssignmentManagementSerializer(
                    assignments,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    match = (
        Match.objects.select_related(
            "competition",
            "competition__league",
            "competition__league__union",
            "home_club",
            "away_club",
        )
        .filter(id=request.data.get("match"))
        .first()
    )
    if match is None:
        return _error("A valid fixture is required.")
    if not _user_can_manage_match(request.user, match):
        return _error(
            "You cannot appoint officials for this competition.",
            status.HTTP_403_FORBIDDEN,
        )

    official = UnionMatchOfficial.objects.filter(
        id=request.data.get("official"),
        union=match.competition.league.union,
    ).first()
    if official is None:
        return _error("Select a union-approved official for this fixture.")
    if official.status != UnionMatchOfficial.Status.AVAILABLE:
        return _error("The selected official is not currently available.")

    fixture_sports = {
        str(match.home_club.sport or "").strip().upper(),
        str(match.away_club.sport or "").strip().upper(),
    }
    if official.primary_sport and official.primary_sport not in fixture_sports:
        return _error("The selected official is not approved for this fixture's sport.")

    role_type = _normalise_role_type(request.data.get("role_type"))
    if role_type is None:
        return _error("Select a valid official role.")

    appointment_status = _admin_status(request.data.get("status"))
    if appointment_status is None or appointment_status == FixtureOfficialAssignment.Status.CANCELLED:
        return _error("New appointments must be PROPOSED or ASSIGNED.")

    with transaction.atomic():
        assignment, created = FixtureOfficialAssignment.objects.update_or_create(
            match=match,
            official=official,
            role_type=role_type,
            defaults={
                "status": appointment_status,
                "notes": str(request.data.get("notes") or "").strip(),
                "response_note": "",
                "responded_at": None,
                "assigned_by": request.user,
            },
        )

        log_governance_action(
            actor=request.user,
            action=(
                "league_fixture_official_assigned"
                if created
                else "league_fixture_official_assignment_updated"
            ),
            details={
                "league": match.competition.league_id,
                "competition": match.competition_id,
                "match": match.id,
                "official": official.id,
                "role_type": role_type,
                "status": assignment.status,
            },
        )

    return Response(
        FixtureOfficialAssignmentManagementSerializer(
            assignment,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_appointment_detail_view(request, assignment_id):
    assignment = _assignment_queryset().filter(id=assignment_id).first()
    if assignment is None:
        return _error("Official appointment not found.", status.HTTP_404_NOT_FOUND)
    if not _user_can_manage_match(request.user, assignment.match):
        return _error(
            "You cannot manage this appointment.", status.HTTP_403_FORBIDDEN
        )

    if request.method == "GET":
        return Response(
            FixtureOfficialAssignmentManagementSerializer(
                assignment,
                context={"request": request},
            ).data
        )

    if request.method == "DELETE":
        if assignment.status in OFFICIAL_RESPONSE_STATUSES:
            return _error(
                "Accepted or declined appointments must be cancelled rather than deleted."
            )
        appointment_id = assignment.id
        assignment.delete()
        log_governance_action(
            actor=request.user,
            action="league_fixture_official_assignment_deleted",
            details={"assignment": appointment_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "status" in request.data:
        next_status = _admin_status(request.data.get("status"))
        if next_status is None:
            return _error(
                "League administrators may only set PROPOSED, ASSIGNED or CANCELLED."
            )
        if (
            assignment.status in OFFICIAL_RESPONSE_STATUSES
            and next_status != FixtureOfficialAssignment.Status.CANCELLED
        ):
            return _error(
                "An official response can only be preserved or cancelled; it cannot be reset by a league administrator."
            )
        assignment.status = next_status
        if next_status in {
            FixtureOfficialAssignment.Status.PROPOSED,
            FixtureOfficialAssignment.Status.ASSIGNED,
        }:
            assignment.response_note = ""
            assignment.responded_at = None

    if "role_type" in request.data:
        role_type = _normalise_role_type(request.data.get("role_type"))
        if role_type is None:
            return _error("Select a valid official role.")
        assignment.role_type = role_type

    if "notes" in request.data:
        assignment.notes = str(request.data.get("notes") or "").strip()

    assignment.assigned_by = request.user
    assignment.save()

    log_governance_action(
        actor=request.user,
        action="league_fixture_official_assignment_updated",
        details={
            "assignment": assignment.id,
            "league": assignment.match.competition.league_id,
            "competition": assignment.match.competition_id,
            "status": assignment.status,
        },
    )

    return Response(
        FixtureOfficialAssignmentManagementSerializer(
            assignment,
            context={"request": request},
        ).data
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def match_official_appointments_view(request):
    assignments = _assignment_queryset().filter(official__user=request.user)

    status_value = request.query_params.get("status")
    if status_value:
        assignments = assignments.filter(status=str(status_value).upper())

    upcoming = str(request.query_params.get("upcoming") or "").lower()
    if upcoming in {"1", "true", "yes"}:
        assignments = assignments.filter(match__match_date__gte=timezone.now())

    return Response(
        {
            "count": assignments.count(),
            "results": FixtureOfficialAssignmentManagementSerializer(
                assignments,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticatedAudit])
def match_official_appointment_response_view(request, assignment_id):
    assignment = (
        _assignment_queryset()
        .filter(id=assignment_id, official__user=request.user)
        .first()
    )
    if assignment is None:
        return _error("Official appointment not found.", status.HTTP_404_NOT_FOUND)

    if assignment.status not in {
        FixtureOfficialAssignment.Status.PROPOSED,
        FixtureOfficialAssignment.Status.ASSIGNED,
    }:
        return _error(
            "Only proposed or assigned appointments can receive a response."
        )

    response_status = str(request.data.get("status") or "").strip().upper()
    if response_status not in OFFICIAL_RESPONSE_STATUSES:
        return _error("The response status must be ACCEPTED or DECLINED.")

    response_note = str(request.data.get("response_note") or "").strip()
    if (
        response_status == FixtureOfficialAssignment.Status.DECLINED
        and not response_note
    ):
        return _error("Please provide a reason when declining an appointment.")

    assignment.status = response_status
    assignment.response_note = response_note
    assignment.responded_at = timezone.now()
    assignment.save(update_fields=[
        "status",
        "response_note",
        "responded_at",
        "updated_at",
    ])

    log_governance_action(
        actor=request.user,
        target_user=request.user,
        action=(
            "match_official_appointment_accepted"
            if response_status == FixtureOfficialAssignment.Status.ACCEPTED
            else "match_official_appointment_declined"
        ),
        details={
            "assignment": assignment.id,
            "league": assignment.match.competition.league_id,
            "competition": assignment.match.competition_id,
            "match": assignment.match_id,
            "official": assignment.official_id,
            "response_note": response_note,
        },
    )

    return Response(
        FixtureOfficialAssignmentManagementSerializer(
            assignment,
            context={"request": request},
        ).data
    )
