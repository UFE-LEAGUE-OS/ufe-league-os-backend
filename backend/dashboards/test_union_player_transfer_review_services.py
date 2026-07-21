from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Club, ClubAdminScope, Notification, User
from teams.models import Team

from .models import (
    ClubAffiliation,
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    League,
    Season,
    Union,
    UnionAuditEvent,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_player_transfer_review_services import (
    TransferReviewValidationError,
    approve_player_transfer_decision,
    reject_player_transfer,
    request_player_transfer_changes,
    validate_player_transfer_for_union_review,
)
from .union_player_transfer_return_services import return_loaned_player_to_source
from .union_player_transfer_services import (
    create_player_transfer_draft,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    submit_player_transfer,
)


class UnionPlayerTransferReviewServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.union = Union.objects.create(
            name="Decision Union",
            slug="decision-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Decision Workspace",
            slug="decision-workspace",
            acronym="DW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Decision League",
            slug="decision-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name=str(self.today.year),
            slug=f"decision-{self.today.year}",
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=180),
        )
        self.player_user = self._user("player", User.Role.FAN)
        self.destination_actor = self._user("destination", User.Role.CLUB_ADMIN)
        self.source_actor = self._user("source", User.Role.CLUB_ADMIN)
        self.reviewer = self._user("reviewer", User.Role.FAN)
        self.no_permission_reviewer = self._user("limited", User.Role.FAN)

        self.source_club = self._club("Source", self.source_actor)
        self.destination_club = self._club("Destination", self.destination_actor)
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Source Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Destination Team",
        )
        for club in (self.source_club, self.destination_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )

        self.player = UnionPlayer.objects.create(
            union=self.union,
            user=self.player_user,
            union_player_number="DU-P000001",
            first_name="Transfer",
            last_name="Player",
            date_of_birth=self.today - timedelta(days=9000),
            nationality="Ugandan",
            identity_reference="PRIVATE-IDENTITY-REFERENCE",
            status=UnionPlayer.Status.APPROVED,
        )
        self.registration = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=self.player,
            club=self.source_club,
            team=self.source_team,
            season=self.season,
            status=UnionPlayerRegistration.Status.ACTIVE,
            registration_type="FIRST_REGISTRATION",
            effective_from=self.today - timedelta(days=120),
            effective_to=self.today + timedelta(days=120),
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )
        self.identity, self.edition = self._competition("primary")
        self.eligibility = UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=self.identity,
            competition_edition=self.edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
            warnings=[
                {
                    "code": "SOURCE_WARNING",
                    "field": "player",
                    "message": "Maintained warning.",
                    "severity": "WARNING",
                    "private_extra": "must not be copied",
                }
            ],
        )
        self.membership = UnionWorkspaceMembership.objects.create(
            user=self.reviewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.no_permission_membership = UnionWorkspaceMembership.objects.create(
            user=self.no_permission_reviewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin):
        club = Club.objects.create(
            name=f"{prefix} Decision Club",
            slug=f"{prefix.lower()}-decision-club",
            admin=admin,
        )
        ClubAdminScope.objects.create(
            user=admin,
            club=club,
            role=ClubAdminScope.Role.CHAIRMAN,
        )
        return club

    def _competition(self, suffix):
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name=f"Decision Cup {suffix}",
            slug=f"decision-cup-{suffix}",
        )
        competition = Competition.objects.create(
            league=self.league,
            name=f"Decision Competition {suffix}",
            slug=f"decision-competition-{suffix}",
            season=str(self.today.year),
            season_record=self.season,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.ACTIVE,
        )
        return identity, edition

    def _submitted(
        self,
        *,
        transfer_type="PERMANENT",
        effective_on=None,
    ):
        transfer = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=self.registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=effective_on or self.today,
            transfer_type=transfer_type,
            loan_end_on=(
                self.today + timedelta(days=30) if transfer_type == "LOAN" else None
            ),
            documents=["PRIVATE-TRANSFER-DOCUMENT"],
            fee_status="PAID",
        )
        return submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )

    def _under_review(
        self,
        *,
        transfer_type="PERMANENT",
        effective_on=None,
        response_status=UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
    ):
        transfer = self._submitted(
            transfer_type=transfer_type,
            effective_on=effective_on,
        )
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=response_status,
            response=(
                "PRIVATE-SOURCE-OBJECTION"
                if response_status
                == UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED
                else "Acknowledged."
            ),
        )
        return record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.player_user,
            consent_method="PLAYER_PORTAL",
        )

    def _approve(self, transfer):
        return approve_player_transfer_decision(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="All maintained transfer requirements are satisfied.",
        )

    def test_active_membership_and_permission_allow_review(self):
        transfer = self._under_review()
        validation = validate_player_transfer_for_union_review(
            transfer=transfer,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        self.assertEqual(validation["version"], 1)
        self.assertEqual(validation["blocking_errors"], [])

    def test_missing_inactive_and_unpermitted_memberships_are_rejected(self):
        transfer = self._under_review()
        with self.assertRaises(ValidationError):
            request_player_transfer_changes(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=None,
                reason="Clarify terms.",
            )
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            request_player_transfer_changes(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Clarify terms.",
            )
        with self.assertRaises(ValidationError):
            request_player_transfer_changes(
                transfer_id=transfer.id,
                reviewer=self.no_permission_reviewer,
                membership=self.no_permission_membership,
                reason="Clarify terms.",
            )

    def test_reviewer_cannot_decide_an_initiated_transfer(self):
        transfer = self._under_review()
        transfer.initiated_by = self.reviewer
        transfer.save(update_fields=["initiated_by"])
        with self.assertRaises(ValidationError):
            reject_player_transfer(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Self-decision is prohibited.",
            )

    def test_source_and_destination_club_scopes_are_both_required(self):
        transfer = self._under_review()
        for club_id in (self.source_club.id, self.destination_club.id):
            with self.subTest(club_id=club_id):
                self.membership.scope_restrictions = {"club_ids": [club_id]}
                self.membership.save(update_fields=["scope_restrictions"])
                with self.assertRaises(ValidationError):
                    request_player_transfer_changes(
                        transfer_id=transfer.id,
                        reviewer=self.reviewer,
                        membership=self.membership,
                        reason="Out-of-scope review.",
                    )
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )

    def test_affected_identity_and_edition_scopes_are_enforced(self):
        transfer = self._under_review()
        base = {
            "club_ids": [self.source_club.id, self.destination_club.id],
        }
        restrictions = [
            {**base, "competition_identity_ids": []},
            {
                **base,
                "competition_identity_ids": [self.identity.id],
                "competition_edition_ids": [],
            },
        ]
        for scope_restrictions in restrictions:
            with self.subTest(scope_restrictions=scope_restrictions):
                self.membership.scope_restrictions = scope_restrictions
                self.membership.save(update_fields=["scope_restrictions"])
                with self.assertRaises(ValidationError):
                    self._approve(transfer)
        self.registration.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )

    def test_request_changes_preserves_authoritative_records(self):
        transfer = self._under_review()
        changed = request_player_transfer_changes(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Update the destination terms.",
        )
        self.assertEqual(
            changed.status,
            UnionPlayerTransfer.Status.CHANGES_REQUESTED,
        )
        self.assertEqual(changed.reviewed_by, self.reviewer)
        self.assertIsNotNone(changed.reviewed_at)
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)

    def test_request_changes_requires_reason_and_under_review_state(self):
        transfer = self._under_review()
        with self.assertRaises(ValidationError):
            request_player_transfer_changes(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason=" ",
            )
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            request_player_transfer_changes(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Repeated request.",
            )

    def test_rejection_stores_fresh_validation_without_movement(self):
        transfer = self._under_review()
        result = reject_player_transfer(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="The Union rejected the maintained evidence.",
        )
        rejected = result["transfer"]
        self.assertEqual(rejected.status, UnionPlayerTransfer.Status.REJECTED)
        self.assertEqual(rejected.reviewed_by, self.reviewer)
        self.assertIn("review_warnings", rejected.automatic_validation)
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        self.assertIsNone(rejected.destination_registration)

    def test_rejection_requires_written_reason(self):
        transfer = self._under_review()
        with self.assertRaises(ValidationError):
            reject_player_transfer(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason=" ",
            )

    def test_player_consent_and_source_response_are_review_blockers(self):
        transfer = self._submitted()
        transfer.status = UnionPlayerTransfer.Status.UNDER_UNION_REVIEW
        transfer.save(update_fields=["status"])
        validation = validate_player_transfer_for_union_review(
            transfer=transfer,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        codes = {item["code"] for item in validation["blocking_errors"]}
        self.assertIn("PLAYER_CONSENT_REQUIRED", codes)
        self.assertIn("SOURCE_CLUB_RESPONSE_REQUIRED", codes)

    def test_source_objection_is_a_warning_not_a_blocker(self):
        transfer = self._under_review(
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
        )
        validation = validate_player_transfer_for_union_review(
            transfer=transfer,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        warning_codes = {item["code"] for item in validation["review_warnings"]}
        blocker_codes = {item["code"] for item in validation["blocking_errors"]}
        self.assertIn("SOURCE_CLUB_OBJECTED", warning_codes)
        self.assertNotIn("SOURCE_CLUB_OBJECTED", blocker_codes)

    def test_future_approval_is_scheduled_without_movement(self):
        transfer = self._under_review(effective_on=self.today + timedelta(days=1))
        result = self._approve(transfer)
        self.assertTrue(result["activation_scheduled"])
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.APPROVED,
        )
        self.assertIsNone(result["destination_registration"])
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )

    def test_due_loan_approval_starts_the_loan(self):
        transfer = self._under_review(transfer_type="LOAN")
        result = self._approve(transfer)
        self.assertFalse(result["activation_scheduled"])
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        )
        self.assertEqual(
            result["destination_registration"].effective_to,
            transfer.loan_end_on,
        )

    def test_inactive_source_registration_blocks_approval(self):
        transfer = self._under_review()
        self.registration.status = UnionPlayerRegistration.Status.SUSPENDED
        self.registration.save(update_fields=["status"])
        with self.assertRaises(TransferReviewValidationError) as context:
            self._approve(transfer)
        codes = {
            item["code"]
            for item in context.exception.automatic_validation["blocking_errors"]
        }
        self.assertIn("SOURCE_REGISTRATION_INACTIVE", codes)

    def test_conflicting_active_registration_blocks_approval(self):
        other_union = Union.objects.create(name="Other Union", slug="other-union")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other Workspace",
            slug="other-workspace",
            acronym="OW",
            sport="Football",
        )
        UnionPlayerRegistration.objects.create(
            workspace=other_workspace,
            player=self.player,
            club=self.destination_club,
            status=UnionPlayerRegistration.Status.ACTIVE,
            effective_from=self.today - timedelta(days=1),
        )
        transfer = self._under_review()
        with self.assertRaises(TransferReviewValidationError) as context:
            self._approve(transfer)
        codes = {
            item["code"]
            for item in context.exception.automatic_validation["blocking_errors"]
        }
        self.assertIn("CONFLICTING_ACTIVE_REGISTRATION", codes)

    def test_permanent_completion_moves_registration_history_correctly(self):
        transfer = self._under_review()
        original_expiry = self.registration.effective_to
        result = self._approve(transfer)
        destination = result["destination_registration"]
        self.registration.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.TRANSFERRED,
        )
        self.assertEqual(
            self.registration.effective_to,
            transfer.effective_on - timedelta(days=1),
        )
        self.assertEqual(destination.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(destination.club, self.destination_club)
        self.assertEqual(destination.team, self.destination_team)
        self.assertEqual(destination.predecessor, self.registration)
        self.assertEqual(destination.effective_from, transfer.effective_on)
        self.assertEqual(destination.effective_to, original_expiry)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.COMPLETED)
        self.assertEqual(transfer.destination_registration, destination)
        self.assertIsNotNone(transfer.completed_at)
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)

    def test_free_transfer_uses_the_same_authoritative_movement(self):
        transfer = self._under_review(transfer_type="FREE_TRANSFER")
        destination = self._approve(transfer)["destination_registration"]
        self.assertEqual(destination.registration_type, "FREE_TRANSFER")
        self.registration.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.TRANSFERRED,
        )

    def test_completion_closes_nonterminal_eligibility_and_creates_pending_history(
        self,
    ):
        created_sources = [self.eligibility]
        for suffix, status in (
            ("pending", UnionPlayerCompetitionEligibility.Status.PENDING),
            ("suspended", UnionPlayerCompetitionEligibility.Status.SUSPENDED),
        ):
            identity, edition = self._competition(suffix)
            created_sources.append(
                UnionPlayerCompetitionEligibility.objects.create(
                    workspace=self.workspace,
                    player=self.player,
                    registration=self.registration,
                    club=self.source_club,
                    team=self.source_team,
                    competition_identity=identity,
                    competition_edition=edition,
                    season=self.season,
                    status=status,
                )
            )
        terminal_identity, terminal_edition = self._competition("terminal")
        terminal = UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=terminal_identity,
            competition_edition=terminal_edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.REJECTED,
        )

        transfer = self._under_review()
        result = self._approve(transfer)
        expected_statuses = {
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
            UnionPlayerCompetitionEligibility.Status.CANCELLED,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        }
        actual_statuses = set()
        for eligibility in created_sources:
            eligibility.refresh_from_db()
            actual_statuses.add(eligibility.status)
        self.assertEqual(actual_statuses, expected_statuses)
        terminal.refresh_from_db()
        self.assertEqual(
            terminal.status,
            UnionPlayerCompetitionEligibility.Status.REJECTED,
        )
        destinations = result["destination_eligibilities"]
        self.assertEqual(len(destinations), 3)
        self.assertTrue(
            all(
                item.status == UnionPlayerCompetitionEligibility.Status.PENDING
                and item.source_transfer_id == transfer.id
                and item.registration == result["destination_registration"]
                and item.reviewed_by is None
                and item.eligible_from is None
                and item.eligible_until is None
                for item in destinations
            )
        )
        copied_warning = destinations[0].warnings[0]
        self.assertNotIn("private_extra", copied_warning)

    def test_completion_replay_is_idempotent(self):
        transfer = self._under_review()
        first = self._approve(transfer)
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        irreversible_actions = {
            "union_player_transfer.approved",
            "union_player_transfer.completed",
            "union_player_registration.transferred_out",
            "union_player_registration.transfer_successor_created",
            "competition_eligibility.closed_for_transfer",
            "competition_eligibility.pending_created_for_transfer",
        }
        audit_count = UnionAuditEvent.objects.filter(
            action__in=irreversible_actions
        ).count()

        replay = self._approve(transfer)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["destination_registration"],
            first["destination_registration"],
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )
        self.assertEqual(
            UnionAuditEvent.objects.filter(action__in=irreversible_actions).count(),
            audit_count,
        )

    def test_approval_replay_routes_completed_loan_return(self):
        transfer = self._under_review(transfer_type="LOAN")
        first = self._approve(transfer)
        returned = return_loaned_player_to_source(
            transfer_id=transfer.id,
            as_of=transfer.loan_end_on + timedelta(days=1),
        )
        replay = self._approve(transfer)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["return_registration"],
            returned["return_registration"],
        )
        self.assertEqual(
            replay["destination_registration"],
            first["destination_registration"],
        )

    def test_completion_audit_metadata_excludes_private_evidence(self):
        transfer = self._under_review(
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
        )
        self._approve(transfer)
        private_values = {
            "PRIVATE-TRANSFER-DOCUMENT",
            "PRIVATE-SOURCE-OBJECTION",
            "PRIVATE-IDENTITY-REFERENCE",
        }
        for metadata in UnionAuditEvent.objects.filter(
            action__in={
                "union_player_transfer.approved",
                "union_player_transfer.completed",
                "union_player_registration.transferred_out",
                "union_player_registration.transfer_successor_created",
                "competition_eligibility.closed_for_transfer",
                "competition_eligibility.pending_created_for_transfer",
            }
        ).values_list("metadata", flat=True):
            for private_value in private_values:
                self.assertNotIn(private_value, str(metadata))

    def test_completion_notification_runs_after_commit_and_excludes_reviewer(self):
        transfer = self._under_review()
        with self.captureOnCommitCallbacks(execute=True):
            self._approve(transfer)
        self.assertTrue(
            Notification.objects.filter(user=self.destination_actor).exists()
        )
        self.assertTrue(Notification.objects.filter(user=self.source_actor).exists())
        self.assertTrue(Notification.objects.filter(user=self.player_user).exists())
        self.assertFalse(Notification.objects.filter(user=self.reviewer).exists())

    def test_notification_failure_does_not_roll_back_completion(self):
        transfer = self._under_review()
        with patch(
            (
                "dashboards.union_player_transfer_review_services."
                "create_in_app_notification"
            ),
            side_effect=RuntimeError("notification unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = self._approve(transfer)
        result["transfer"].refresh_from_db()
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.COMPLETED,
        )
        self.assertEqual(
            result["destination_registration"].status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
