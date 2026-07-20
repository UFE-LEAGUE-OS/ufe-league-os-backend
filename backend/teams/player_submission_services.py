"""Club-owned player submission transitions; Union decisions remain external."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, Value
from django.db.models.functions import Concat
from django.utils import timezone

from accounts.rbac import get_user_clubs
from dashboards.models import UnionPlayer, UnionPlayerRegistration, UnionWorkspace
from dashboards.union_governance import log_union_audit_event
from dashboards.union_players import create_or_find_provisional_player
from dashboards.union_scopes import scope_allows

from .models import PlayerRegistration


def _club_workspace(club, workspace_id=None):
    eligible_workspaces = UnionWorkspace.objects.filter(
        related_union__leagues__club_memberships__club=club,
        status=UnionWorkspace.Status.ACTIVE,
        related_union__isnull=False,
    ).distinct()

    if workspace_id is not None:
        try:
            return eligible_workspaces.get(pk=workspace_id)
        except UnionWorkspace.DoesNotExist as exc:
            raise ValidationError(
                {
                    "union_workspace_id": (
                        "The selected Union workspace does not govern this Club."
                    )
                }
            ) from exc

    workspaces = list(eligible_workspaces.order_by("pk")[:2])
    if not workspaces:
        raise ValidationError(
            {
                "union_workspace_id": (
                    "This Club is not attached to an active Union workspace."
                )
            }
        )
    if len(workspaces) > 1:
        raise ValidationError(
            {
                "union_workspace_id": (
                    "This Club belongs to multiple active Union workspaces. "
                    "Select one explicitly."
                )
            }
        )
    return workspaces[0]


def _assert_club_actor(actor, club):
    if not get_user_clubs(actor).filter(pk=club.pk).exists():
        raise ValidationError({"club": "You do not administer this Club."})


def search_union_players_for_club(
    *,
    actor,
    club,
    query,
    date_of_birth=None,
    union_workspace_id=None,
    limit=20,
):
    _assert_club_actor(actor, club)
    workspace = _club_workspace(club, union_workspace_id)
    search_text = str(query or "").strip()
    if not search_text and date_of_birth is None:
        raise ValidationError(
            {"query": "Enter a player name, player number, or date of birth."}
        )
    try:
        result_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"limit": "Enter a valid result limit."}) from exc
    if result_limit < 1 or result_limit > 50:
        raise ValidationError({"limit": "Result limit must be between 1 and 50."})

    active_registrations = UnionPlayerRegistration.objects.filter(
        workspace=workspace,
        status=UnionPlayerRegistration.Status.ACTIVE,
    ).select_related("club")
    players = UnionPlayer.objects.filter(
        union=workspace.related_union
    ).prefetch_related(
        Prefetch(
            "club_registration_history",
            queryset=active_registrations,
            to_attr="active_club_registrations",
        )
    )
    if search_text:
        players = players.annotate(
            searchable_full_name=Concat("first_name", Value(" "), "last_name")
        ).filter(
            Q(union_player_number__icontains=search_text)
            | Q(first_name__icontains=search_text)
            | Q(last_name__icontains=search_text)
            | Q(searchable_full_name__icontains=search_text)
        )
    if date_of_birth is not None:
        players = players.filter(date_of_birth=date_of_birth)

    results = []
    for player in players.order_by("union_player_number", "id")[:result_limit]:
        selectable, warning = _player_selectability(player.status)
        active_registration = next(
            iter(getattr(player, "active_club_registrations", [])), None
        )
        current_club = None
        if active_registration is not None:
            current_club = {
                "id": active_registration.club_id,
                "name": active_registration.club.name,
            }
        results.append(
            {
                "id": player.id,
                "union_player_number": player.union_player_number,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "full_name": player.full_name,
                "date_of_birth": player.date_of_birth,
                "nationality": player.nationality,
                "status": player.status,
                "can_be_selected": selectable,
                "selection_warning": warning,
                "current_club_summary": current_club,
            }
        )
    return results


def _player_selectability(player_status):
    if player_status == UnionPlayer.Status.APPROVED:
        return True, None
    if player_status == UnionPlayer.Status.PROVISIONAL:
        return True, "This player identity is provisional and requires Union review."
    if player_status == UnionPlayer.Status.PENDING_VERIFICATION:
        return True, "This player identity is pending Union verification."
    return False, "This player identity is not currently selectable."


def _validation_item(code, field, message, severity):
    return {
        "code": code,
        "field": field,
        "message": message,
        "severity": severity,
    }


def _build_player_registration_validation(submission):
    blocking_errors = []
    review_warnings = []
    passed_checks = []
    capability_notes = []

    def error(code, field, message):
        blocking_errors.append(_validation_item(code, field, message, "ERROR"))

    def warning(code, field, message):
        review_warnings.append(_validation_item(code, field, message, "WARNING"))

    def passed(code, field, message):
        passed_checks.append(_validation_item(code, field, message, "PASS"))

    def capability(code, field, message):
        if not any(item["code"] == code for item in capability_notes):
            capability_notes.append(_validation_item(code, field, message, "INFO"))

    workspace = submission.union_workspace
    workspace_is_valid = bool(
        workspace
        and workspace.status == UnionWorkspace.Status.ACTIVE
        and workspace.related_union_id
        and UnionWorkspace.objects.filter(
            pk=workspace.pk,
            status=UnionWorkspace.Status.ACTIVE,
            related_union__leagues__club_memberships__club_id=submission.club_id,
        ).exists()
    )
    if workspace_is_valid:
        passed(
            "WORKSPACE_VALID",
            "union_workspace",
            "The Union workspace governs this Club.",
        )
    else:
        error(
            "WORKSPACE_INVALID",
            "union_workspace",
            "The selected Union workspace does not govern this Club.",
        )
    union_id = workspace.related_union_id if workspace_is_valid else None

    if submission.team_id and submission.team.club_id == submission.club_id:
        passed("TEAM_CLUB_VALID", "team", "Team belongs to the submission Club.")
    else:
        error("TEAM_CLUB_INVALID", "team", "Team must belong to the submission Club.")

    if submission.season_record_id is None:
        error("SEASON_REQUIRED", "season_record", "A season is required.")
    elif union_id and submission.season_record.league.union_id == union_id:
        passed(
            "SEASON_VALID",
            "season_record",
            "Season belongs to the selected Union structure.",
        )
    else:
        error(
            "SEASON_UNION_INVALID",
            "season_record",
            "Season must belong to the selected Union structure.",
        )

    documents = submission.supporting_documents or []
    if any(
        bool(document) and (not isinstance(document, str) or bool(document.strip()))
        for document in documents
    ):
        passed(
            "DOCUMENTS_PRESENT",
            "supporting_documents",
            "At least one supporting document reference is present.",
        )
    else:
        error(
            "SUPPORTING_DOCUMENTS_REQUIRED",
            "supporting_documents",
            "At least one supporting document reference is required.",
        )

    player = submission.union_player
    if player is None:
        error(
            "PLAYER_IDENTITY_REQUIRED", "union_player", "A player identity is required."
        )
    elif union_id and player.union_id != union_id:
        error(
            "PLAYER_UNION_INVALID",
            "union_player",
            "Player identity must belong to the submission Union.",
        )
    elif player.status in {
        UnionPlayer.Status.SUSPENDED,
        UnionPlayer.Status.REJECTED,
        UnionPlayer.Status.ARCHIVED,
    }:
        error(
            f"PLAYER_{player.status}",
            "union_player",
            "Player identity is not currently eligible for submission.",
        )
    else:
        passed(
            "PLAYER_IDENTITY_VALID",
            "union_player",
            "Player identity belongs to the submission Union.",
        )
        if player.status == UnionPlayer.Status.PROVISIONAL:
            warning(
                "PLAYER_IDENTITY_PROVISIONAL",
                "union_player",
                "Player identity remains provisional and requires Union review.",
            )
        elif player.status == UnionPlayer.Status.PENDING_VERIFICATION:
            warning(
                "PLAYER_IDENTITY_PENDING_VERIFICATION",
                "union_player",
                "Player identity is pending Union verification.",
            )

    requested_editions = list(
        submission.requested_competition_editions.select_related(
            "identity", "season"
        ).all()
    )
    editions_are_valid = True
    for edition in requested_editions:
        if not union_id or edition.identity.union_id != union_id:
            editions_are_valid = False
            error(
                "COMPETITION_EDITION_UNION_INVALID",
                "requested_competition_editions",
                "Every competition edition must belong to the submission Union.",
            )
            break
        if (
            submission.season_record_id is None
            or edition.season_id != submission.season_record_id
        ):
            editions_are_valid = False
            error(
                "COMPETITION_EDITION_SEASON_INVALID",
                "requested_competition_editions",
                "Every competition edition must match the selected season.",
            )
            break
    if not requested_editions:
        warning(
            "NO_COMPETITION_EDITION_REQUESTED",
            "requested_competition_editions",
            "No competition edition was requested.",
        )
    elif editions_are_valid:
        passed(
            "COMPETITION_EDITIONS_VALID",
            "requested_competition_editions",
            "Requested competition editions match the Union and season.",
        )

    if submission.registered_date is None:
        error(
            "REGISTERED_DATE_REQUIRED",
            "registered_date",
            "A registration date is required.",
        )
    elif (
        submission.expiry_date is not None
        and submission.expiry_date < submission.registered_date
    ):
        error(
            "REGISTRATION_DATE_ORDER_INVALID",
            "expiry_date",
            "Expiry date cannot precede the registration date.",
        )
    else:
        passed(
            "REGISTRATION_DATES_VALID",
            "registered_date",
            "Registration dates are valid.",
        )

    supported_registration_types = {
        value for value, _label in PlayerRegistration.RegistrationType.choices
    }
    if submission.registration_type not in supported_registration_types:
        error(
            "REGISTRATION_TYPE_INVALID",
            "registration_type",
            "Registration type is not supported.",
        )
    else:
        passed(
            "REGISTRATION_TYPE_VALID",
            "registration_type",
            "Registration type is supported.",
        )
        if (
            submission.registration_type
            == PlayerRegistration.RegistrationType.DUAL_REGISTRATION
        ):
            warning(
                "DUAL_REGISTRATION_RULES_LIMITED",
                "registration_type",
                "Full dual-registration rules are not yet available.",
            )

    non_terminal_statuses = {
        PlayerRegistration.SubmissionStatus.DRAFT,
        PlayerRegistration.SubmissionStatus.SUBMITTED,
        PlayerRegistration.SubmissionStatus.UNDER_AUTOMATIC_REVIEW,
        PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
        PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED,
    }
    if (
        submission.union_player_id
        and submission.club_id
        and submission.season_record_id
        and PlayerRegistration.objects.filter(
            union_player_id=submission.union_player_id,
            club_id=submission.club_id,
            season_record_id=submission.season_record_id,
            submission_status__in=non_terminal_statuses,
        )
        .exclude(pk=submission.pk)
        .exists()
    ):
        error(
            "DUPLICATE_PENDING_SUBMISSION",
            "union_player",
            "Another non-terminal submission exists for this player, Club, and season.",
        )
    else:
        passed(
            "NO_DUPLICATE_PENDING_SUBMISSION",
            "union_player",
            "No duplicate non-terminal submission was found.",
        )

    if (
        submission.registration_number
        and PlayerRegistration.objects.filter(
            registration_number__iexact=submission.registration_number
        )
        .exclude(pk=submission.pk)
        .exists()
    ):
        error(
            "DUPLICATE_REGISTRATION_NUMBER",
            "registration_number",
            "Another player registration uses this registration number.",
        )
    else:
        passed(
            "REGISTRATION_NUMBER_AVAILABLE",
            "registration_number",
            "Registration number is available.",
        )

    if (
        submission.union_player_id
        and UnionPlayerRegistration.objects.filter(player_id=submission.union_player_id)
        .exclude(source_registration_id=submission.pk)
        .exists()
    ):
        warning(
            "PLAYER_HAS_REGISTRATION_HISTORY",
            "union_player",
            "Historical Union registration records exist for this player.",
        )

    capability(
        "REGISTRATION_FEE_CHECK_UNAVAILABLE",
        None,
        "Registration-fee verification is not yet available.",
    )
    capability(
        "PLAYER_SUSPENSION_DETAIL_CHECK_LIMITED",
        "union_player",
        "Detailed suspension-rule evaluation is not yet available.",
    )
    capability(
        "TRANSFER_WINDOW_RULE_ENGINE_UNAVAILABLE",
        "transfer_window",
        "Transfer-window rule evaluation is not yet available.",
    )
    capability(
        "SQUAD_LIMIT_CHECK_UNAVAILABLE",
        "team",
        "Squad-limit evaluation is not yet available.",
    )

    return {
        "blocking_errors": blocking_errors,
        "review_warnings": review_warnings,
        "passed_checks": passed_checks,
        "capability_notes": capability_notes,
        "evaluated_at": timezone.now().isoformat(),
        "version": 1,
    }


def validate_player_registration_submission(*, submission, actor):
    result = _build_player_registration_validation(submission)
    if get_user_clubs(actor).filter(pk=submission.club_id).exists():
        result["passed_checks"].insert(
            0,
            _validation_item(
                "CLUB_SCOPE_VALID",
                "club",
                "Club administration scope is valid.",
                "PASS",
            ),
        )
    else:
        result["blocking_errors"].insert(
            0,
            _validation_item(
                "CLUB_SCOPE_INVALID",
                "club",
                "The actor does not actively administer this Club.",
                "ERROR",
            ),
        )
    return result


def validate_player_registration_for_union_review(
    *,
    submission,
    reviewer,
    membership,
    required_permission="union.registrations.manage",
    final_decision=False,
):
    result = _build_player_registration_validation(submission)

    def error(code, field, message):
        if not any(item["code"] == code for item in result["blocking_errors"]):
            result["blocking_errors"].append(
                _validation_item(code, field, message, "ERROR")
            )

    def passed(code, field, message):
        if not any(item["code"] == code for item in result["passed_checks"]):
            result["passed_checks"].append(
                _validation_item(code, field, message, "PASS")
            )

    membership_is_active = bool(
        membership
        and getattr(membership, "pk", None)
        and membership.__class__.objects.filter(
            pk=membership.pk,
            user=reviewer,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            workspace__related_union__isnull=False,
        ).exists()
    )
    if membership_is_active:
        passed(
            "UNION_MEMBERSHIP_VALID",
            "workspace",
            "Reviewer has an active membership in the selected workspace.",
        )
    else:
        error(
            "UNION_MEMBERSHIP_INVALID",
            "workspace",
            "An active Union workspace membership is required.",
        )

    reviewer_is_super_admin = bool(
        reviewer
        and (
            getattr(reviewer, "is_superuser", False)
            or getattr(reviewer, "role", None) == "SUPER_ADMIN"
        )
    )
    if reviewer_is_super_admin or (
        membership_is_active and required_permission in membership.effective_permissions
    ):
        passed(
            "UNION_PERMISSION_VALID",
            None,
            f"Reviewer has {required_permission}.",
        )
    else:
        error(
            "UNION_PERMISSION_DENIED",
            None,
            f"Reviewer requires {required_permission}.",
        )

    workspace = membership.workspace if membership_is_active else None
    if workspace is None or submission.union_workspace_id != workspace.id:
        error(
            "REVIEW_WORKSPACE_INVALID",
            "union_workspace",
            "Submission does not belong to the selected Union workspace.",
        )
    else:
        passed(
            "REVIEW_WORKSPACE_VALID",
            "union_workspace",
            "Submission belongs to the selected Union workspace.",
        )

    if membership_is_active and not scope_allows(
        membership, "club", submission.club_id
    ):
        error(
            "REVIEW_CLUB_SCOPE_DENIED",
            "club",
            "Submission Club is outside the reviewer scope.",
        )
    elif membership_is_active:
        passed(
            "REVIEW_CLUB_SCOPE_VALID",
            "club",
            "Submission Club is within the reviewer scope.",
        )

    requested_editions = list(
        submission.requested_competition_editions.select_related("identity").all()
    )
    if membership_is_active:
        for edition in requested_editions:
            if not scope_allows(
                membership, "competition_identity", edition.identity_id
            ) or not scope_allows(membership, "competition_edition", edition.id):
                error(
                    "REVIEW_COMPETITION_SCOPE_DENIED",
                    "requested_competition_editions",
                    "A requested competition is outside the reviewer scope.",
                )
                break
        else:
            passed(
                "REVIEW_COMPETITION_SCOPE_VALID",
                "requested_competition_editions",
                "Requested competitions are within the reviewer scope.",
            )

    if submission.submission_status not in {
        PlayerRegistration.SubmissionStatus.SUBMITTED,
        PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
    }:
        error(
            "REVIEW_STATUS_INVALID",
            "submission_status",
            "Submission is not in a reviewable status.",
        )

    if final_decision and submission.submitted_by_id == getattr(reviewer, "pk", None):
        error(
            "REVIEWER_IS_SUBMITTER",
            "reviewer",
            "The original Club submitter cannot make the final Union decision.",
        )

    player = submission.union_player
    active_registrations = (
        UnionPlayerRegistration.objects.filter(
            workspace=workspace,
            player=player,
            status=UnionPlayerRegistration.Status.ACTIVE,
        )
        if workspace is not None and player is not None
        else UnionPlayerRegistration.objects.none()
    )
    registration_type = submission.registration_type
    if registration_type in {
        PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
        PlayerRegistration.RegistrationType.FREE_AGENT_REGISTRATION,
    }:
        if active_registrations.exists():
            error(
                "ACTIVE_REGISTRATION_CONFLICT",
                "union_player",
                "Player already has an active authoritative registration.",
            )
    elif registration_type == PlayerRegistration.RegistrationType.SEASON_RENEWAL:
        previous = active_registrations.select_related("season").first()
        if previous is None:
            error(
                "RENEWAL_ACTIVE_REGISTRATION_REQUIRED",
                "union_player",
                "Season renewal requires an active authoritative registration.",
            )
        elif previous.club_id != submission.club_id:
            error(
                "RENEWAL_CLUB_CONFLICT",
                "club",
                "Season renewal must remain with the active registration Club.",
            )
        else:
            if (
                previous.season_id
                and submission.season_record_id
                and previous.season_id == submission.season_record_id
            ):
                error(
                    "RENEWAL_SEASON_CONFLICT",
                    "season_record",
                    "Season renewal must use a different season.",
                )
            if submission.registered_date <= previous.effective_from:
                error(
                    "RENEWAL_DATE_INVALID",
                    "registered_date",
                    "Renewal effective date must follow the previous registration.",
                )
    elif (
        registration_type
        == PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
    ):
        if not active_registrations.filter(club_id=submission.club_id).exists():
            error(
                "COMPETITION_REGISTRATION_ACTIVE_CLUB_REQUIRED",
                "club",
                "Competition registration requires an active registration for this Club.",
            )
    elif registration_type == PlayerRegistration.RegistrationType.DUAL_REGISTRATION:
        error(
            "DUAL_REGISTRATION_UNAVAILABLE",
            "registration_type",
            "Full dual-registration rules are not yet implemented.",
        )

    return result


class SubmissionValidationError(ValidationError):
    def __init__(self, automatic_validation):
        super().__init__(
            {
                "detail": (
                    "Player registration submission contains blocking validation errors."
                )
            }
        )
        self.automatic_validation = automatic_validation


def _store_validation_result(*, submission, actor, validation_result):
    submission.automatic_validation = validation_result
    submission.save(update_fields=["automatic_validation", "updated_at"])
    if submission.union_workspace_id:
        log_union_audit_event(
            workspace=submission.union_workspace,
            actor=actor,
            action="player_registration.validation_completed",
            target=submission,
            metadata={
                "blocking_error_count": len(validation_result["blocking_errors"]),
                "review_warning_count": len(validation_result["review_warnings"]),
                "capability_note_count": len(validation_result["capability_notes"]),
                "validation_version": validation_result["version"],
            },
        )


@transaction.atomic
def create_player_registration_draft(*, actor, validated_data, audit_metadata=None):
    club = validated_data["club"]
    team = validated_data["team"]
    _assert_club_actor(actor, club)
    if team.club_id != club.id:
        raise ValidationError({"team": "Team must belong to the selected Club."})
    draft_data = validated_data.copy()
    workspace = _club_workspace(club, draft_data.pop("union_workspace_id", None))
    requested_editions = list(draft_data.pop("requested_competition_editions", []))
    existing_player_id = draft_data.pop("existing_union_player_id", None)
    identity_reference = draft_data.pop("identity_reference", "")
    if existing_player_id:
        if identity_reference:
            raise ValidationError(
                {
                    "existing_union_player_id": "Do not combine an existing player with identity reference input."
                }
            )
        player = UnionPlayer.objects.filter(
            pk=existing_player_id, union=workspace.related_union
        ).first()
        if player is None or player.status in {
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        }:
            raise ValidationError(
                {"existing_union_player_id": "Player is not selectable in this Union."}
            )
        log_union_audit_event(
            workspace=workspace,
            actor=actor,
            action="union_player.existing_identity_selected",
            target=player,
        )
    else:
        player, _ = create_or_find_provisional_player(
            workspace=workspace,
            actor=actor,
            first_name=draft_data["first_name"],
            last_name=draft_data["last_name"],
            date_of_birth=draft_data["date_of_birth"],
            nationality=draft_data["nationality"],
            identity_reference=identity_reference,
        )
    draft = PlayerRegistration.objects.create(
        **draft_data,
        union_workspace=workspace,
        union_player=player,
        status=PlayerRegistration.RegistrationStatus.INACTIVE,
        submission_status=PlayerRegistration.SubmissionStatus.DRAFT,
    )
    for edition in requested_editions:
        if edition.identity.union_id != workspace.related_union_id:
            raise ValidationError(
                {"requested_competition_editions": "Edition is outside this Union."}
            )
        if draft.season_record_id and edition.season_id != draft.season_record_id:
            raise ValidationError(
                {
                    "requested_competition_editions": "Edition must match the selected season."
                }
            )
    draft.requested_competition_editions.set(requested_editions)
    log_union_audit_event(
        workspace=workspace,
        actor=actor,
        action="player_registration.draft_created",
        target=draft,
        metadata=audit_metadata,
    )
    return draft


@transaction.atomic
def update_player_registration_draft(*, submission_id, actor, updates):
    submission = (
        PlayerRegistration.objects.select_for_update()
        .select_related("club")
        .get(pk=submission_id)
    )
    _assert_club_actor(actor, submission.club)
    if submission.submission_status not in {
        PlayerRegistration.SubmissionStatus.DRAFT,
        PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED,
    }:
        raise ValidationError(
            {"status": "Only draft or change-requested submissions may be edited."}
        )
    forbidden = {
        "club",
        "submission_status",
        "union_workspace",
        "union_player",
        "submitted_by",
        "submitted_at",
        "last_resubmitted_at",
        "assigned_reviewer",
        "change_request_reason",
        "union_decision_reason",
        "reviewed_at",
        "automatic_validation",
        "submission_revision",
        "withdrawal_reason",
        "status",
        "user",
    }
    update_data = updates.copy()
    editions_not_supplied = object()
    supplied_editions = update_data.pop(
        "requested_competition_editions", editions_not_supplied
    )
    attempted = forbidden.intersection(update_data)
    if attempted:
        raise ValidationError({"fields": f"Club cannot update: {sorted(attempted)}."})
    if "team" in update_data and update_data["team"].club_id != submission.club_id:
        raise ValidationError({"team": "Team must belong to the submission Club."})

    selected_season = update_data.get("season_record", submission.season_record)
    if supplied_editions is editions_not_supplied:
        editions_to_validate = list(submission.requested_competition_editions.all())
    else:
        editions_to_validate = list(supplied_editions)

    unique_editions = {}
    for edition in editions_to_validate:
        unique_editions[edition.pk] = edition
    requested_editions = list(unique_editions.values())
    for edition in requested_editions:
        if edition.identity.union_id != submission.union_workspace.related_union_id:
            raise ValidationError(
                {"requested_competition_editions": "Edition is outside this Union."}
            )
        if selected_season is None or edition.season_id != selected_season.pk:
            raise ValidationError(
                {
                    "requested_competition_editions": "Edition must match the selected season."
                }
            )

    for field, value in update_data.items():
        setattr(submission, field, value)
    submission.save(update_fields=[*update_data.keys(), "updated_at"])
    if supplied_editions is not editions_not_supplied:
        submission.requested_competition_editions.set(requested_editions)
    log_union_audit_event(
        workspace=submission.union_workspace,
        actor=actor,
        action="player_registration.draft_updated",
        target=submission,
    )
    return submission


def submit_player_registration(*, submission_id, actor):
    validation_error = None
    with transaction.atomic():
        submission = PlayerRegistration.objects.select_for_update().get(
            pk=submission_id
        )
        _assert_club_actor(actor, submission.club)
        if submission.submission_status != PlayerRegistration.SubmissionStatus.DRAFT:
            raise ValidationError({"status": "Only drafts may be submitted."})
        validation_result = validate_player_registration_submission(
            submission=submission,
            actor=actor,
        )
        _store_validation_result(
            submission=submission,
            actor=actor,
            validation_result=validation_result,
        )
        if validation_result["blocking_errors"]:
            validation_error = SubmissionValidationError(validation_result)
        else:
            submission.submission_status = PlayerRegistration.SubmissionStatus.SUBMITTED
            submission.submitted_by = actor
            submission.submitted_at = timezone.now()
            submission.submission_revision += 1
            submission.save(
                update_fields=[
                    "submission_status",
                    "submitted_by",
                    "submitted_at",
                    "submission_revision",
                    "updated_at",
                ]
            )
            log_union_audit_event(
                workspace=submission.union_workspace,
                actor=actor,
                action="player_registration.submitted",
                target=submission,
            )
    if validation_error is not None:
        raise validation_error
    return submission


def resubmit_player_registration(*, submission_id, actor):
    validation_error = None
    with transaction.atomic():
        submission = PlayerRegistration.objects.select_for_update().get(
            pk=submission_id
        )
        _assert_club_actor(actor, submission.club)
        if (
            submission.submission_status
            != PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        ):
            raise ValidationError(
                {"status": "Only change-requested submissions may be resubmitted."}
            )
        validation_result = validate_player_registration_submission(
            submission=submission,
            actor=actor,
        )
        _store_validation_result(
            submission=submission,
            actor=actor,
            validation_result=validation_result,
        )
        if validation_result["blocking_errors"]:
            validation_error = SubmissionValidationError(validation_result)
        else:
            submission.submission_status = PlayerRegistration.SubmissionStatus.SUBMITTED
            submission.last_resubmitted_at = timezone.now()
            submission.submission_revision += 1
            submission.save(
                update_fields=[
                    "submission_status",
                    "last_resubmitted_at",
                    "submission_revision",
                    "updated_at",
                ]
            )
            log_union_audit_event(
                workspace=submission.union_workspace,
                actor=actor,
                action="player_registration.resubmitted",
                target=submission,
            )
    if validation_error is not None:
        raise validation_error
    return submission


@transaction.atomic
def withdraw_player_registration(*, submission_id, actor, withdrawal_reason):
    submission = PlayerRegistration.objects.select_for_update().get(pk=submission_id)
    _assert_club_actor(actor, submission.club)
    if submission.submission_status not in {
        PlayerRegistration.SubmissionStatus.DRAFT,
        PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED,
        PlayerRegistration.SubmissionStatus.SUBMITTED,
    }:
        raise ValidationError({"status": "This submission cannot be withdrawn."})
    if not withdrawal_reason.strip():
        raise ValidationError({"withdrawal_reason": "A withdrawal reason is required."})
    previous = submission.submission_status
    submission.submission_status = PlayerRegistration.SubmissionStatus.WITHDRAWN
    submission.withdrawal_reason = withdrawal_reason.strip()
    submission.save(
        update_fields=["submission_status", "withdrawal_reason", "updated_at"]
    )
    log_union_audit_event(
        workspace=submission.union_workspace,
        actor=actor,
        action="player_registration.withdrawn",
        target=submission,
        metadata={"from_status": previous},
    )
    return submission
