from datetime import date
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
from .union_player_transfer_services import (
    TransferSubmissionValidationError,
    cancel_player_transfer_request,
    create_player_transfer_draft,
    decline_player_transfer_consent,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    resubmit_player_transfer,
    submit_player_transfer,
    update_player_transfer_draft,
    validate_player_transfer_submission,
)


class UnionPlayerTransferSubmissionServiceTests(TestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Transfer Union",
            slug="transfer-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Transfer Workspace",
            slug="transfer-workspace",
            acronym="TW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Transfer League",
            slug="transfer-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026",
            slug="transfer-2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.player_user = self._user("player", User.Role.FAN)
        self.destination_actor = self._user("destination", User.Role.CLUB_ADMIN)
        self.source_actor = self._user("source", User.Role.CLUB_ADMIN)
        self.no_permission_actor = self._user(
            "no-permission",
            User.Role.CLUB_ADMIN,
        )
        self.outside_actor = self._user("outside", User.Role.CLUB_ADMIN)
        self.union_officer = self._user("union-officer", User.Role.FAN)

        self.source_club = self._club("Source", self.source_actor)
        self.destination_club = self._club("Destination", self.destination_actor)
        self.no_permission_club = self._club(
            "No Permission",
            self.no_permission_actor,
        )
        self.outside_club = self._club("Outside", self.outside_actor)
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Source First Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Destination First Team",
        )
        self.outside_team = Team.objects.create(
            club=self.outside_club,
            name="Outside First Team",
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
            union_player_number="TU-P000001",
            first_name="Martha",
            last_name="Auma",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
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
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            approved_by=self.union_officer,
            approved_at=timezone.now(),
        )
        self.identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Transfer Cup",
            slug="transfer-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Transfer Cup 2026",
            slug="transfer-cup-2026",
            season="2026",
            season_record=self.season,
        )
        self.edition = CompetitionEdition.objects.create(
            identity=self.identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.ACTIVE,
        )
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
        )
        self.officer_membership = UnionWorkspaceMembership.objects.create(
            user=self.union_officer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.REGISTRAR,
        )

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin):
        club = Club.objects.create(
            name=f"{prefix} Transfer Club",
            slug=f"{prefix.lower()}-transfer-club",
            admin=admin,
        )
        role = (
            ClubAdminScope.Role.CLUB_ADMIN
            if admin == self.no_permission_actor
            else ClubAdminScope.Role.CHAIRMAN
        )
        ClubAdminScope.objects.create(
            user=admin,
            club=club,
            role=role,
        )
        return club

    def _draft(self, **overrides):
        values = {
            "actor": self.destination_actor,
            "workspace": self.workspace,
            "source_registration": self.registration,
            "destination_club": self.destination_club,
            "destination_team": self.destination_team,
            "effective_on": date(2026, 7, 1),
            "transfer_type": "PERMANENT",
            "documents": ["transfer-document-reference"],
            "fee_status": "PAID",
        }
        values.update(overrides)
        return create_player_transfer_draft(**values)

    def _submitted(self, **draft_overrides):
        transfer = self._draft(**draft_overrides)
        return submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )

    def test_destination_actor_creates_draft_without_mutating_authority(self):
        registration_status = self.registration.status
        eligibility_status = self.eligibility.status
        transfer = self._draft()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.DRAFT)
        self.assertEqual(transfer.initiated_by, self.destination_actor)
        self.assertEqual(
            transfer.source_club_response_status,
            UnionPlayerTransfer.SourceClubResponseStatus.PENDING,
        )
        self.assertEqual(
            transfer.player_consent_status,
            UnionPlayerTransfer.PlayerConsentStatus.PENDING,
        )
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.assertEqual(self.registration.status, registration_status)
        self.assertEqual(self.eligibility.status, eligibility_status)
        self.assertIsNone(transfer.legacy_transfer)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="union_player_transfer.draft_created"
            ).exists()
        )

    def test_draft_actor_permission_and_club_scope_are_enforced(self):
        with self.assertRaises(ValidationError):
            self._draft(
                actor=self.no_permission_actor,
                destination_club=self.no_permission_club,
            )
        with self.assertRaises(ValidationError):
            self._draft(actor=self.outside_actor)

    def test_draft_rejects_same_club_and_unaffiliated_destination(self):
        with self.assertRaises(ValidationError):
            self._draft(
                actor=self.source_actor,
                destination_club=self.source_club,
                destination_team=self.source_team,
            )
        with self.assertRaises(ValidationError):
            self._draft(
                actor=self.outside_actor,
                destination_club=self.outside_club,
                destination_team=self.outside_team,
            )

    def test_draft_rejects_inactive_registration_and_nonapproved_player(self):
        self.registration.status = UnionPlayerRegistration.Status.SUSPENDED
        self.registration.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            self._draft()
        self.registration.status = UnionPlayerRegistration.Status.ACTIVE
        self.registration.save(update_fields=["status"])
        self.player.status = UnionPlayer.Status.SUSPENDED
        self.player.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            self._draft()

    def test_draft_rejects_invalid_team_and_effective_dates(self):
        with self.assertRaises(ValidationError):
            self._draft(destination_team=self.outside_team)
        for effective_on in (date(2026, 1, 1), date(2027, 1, 1)):
            with self.subTest(effective_on=effective_on):
                with self.assertRaises(ValidationError):
                    self._draft(effective_on=effective_on)

    def test_transfer_type_and_loan_rules_are_explicit(self):
        loan = self._draft(
            transfer_type="LOAN",
            loan_end_on=date(2026, 10, 1),
        )
        self.assertEqual(loan.transfer_type, "LOAN")
        loan.status = UnionPlayerTransfer.Status.CANCELLED
        loan.save(update_fields=["status"])
        cases = [
            {"transfer_type": "LOAN"},
            {
                "transfer_type": "LOAN",
                "loan_end_on": date(2026, 6, 1),
            },
            {
                "transfer_type": "PERMANENT",
                "loan_end_on": date(2026, 10, 1),
            },
            {"transfer_type": "END_OF_LOAN"},
        ]
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    self._draft(**values)
        with self.assertRaisesMessage(
            ValidationError,
            "Loan end date must precede the source registration expiry.",
        ):
            self._draft(
                transfer_type="LOAN",
                loan_end_on=self.registration.effective_to,
            )

    def test_duplicate_nonterminal_transfer_is_rejected(self):
        self._draft()
        with self.assertRaises(ValidationError):
            self._draft()

    def test_destination_club_updates_only_editable_draft_fields(self):
        transfer = self._draft()
        updated = update_player_transfer_draft(
            transfer_id=transfer.id,
            actor=self.destination_actor,
            updates={
                "effective_on": date(2026, 8, 1),
                "documents": ["replacement-reference"],
                "fee_status": "SETTLED",
            },
        )
        self.assertEqual(updated.effective_on, date(2026, 8, 1))
        self.assertEqual(updated.documents, ["replacement-reference"])
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="union_player_transfer.draft_updated"
            ).exists()
        )
        with self.assertRaises(ValidationError):
            update_player_transfer_draft(
                transfer_id=transfer.id,
                actor=self.destination_actor,
                updates={"status": UnionPlayerTransfer.Status.APPROVED},
            )

    def test_draft_update_revalidates_and_submitted_row_is_immutable(self):
        transfer = self._draft()
        with self.assertRaises(ValidationError):
            update_player_transfer_draft(
                transfer_id=transfer.id,
                actor=self.destination_actor,
                updates={"destination_team": self.outside_team},
            )
        submitted = submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        with self.assertRaises(ValidationError):
            update_player_transfer_draft(
                transfer_id=submitted.id,
                actor=self.destination_actor,
                updates={"effective_on": date(2026, 9, 1)},
            )

    def test_structured_validation_reports_warnings_and_capabilities(self):
        transfer = self._draft(
            destination_team=None,
            fee_status="",
        )
        result = validate_player_transfer_submission(
            transfer=transfer,
            actor=self.destination_actor,
        )
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["blocking_errors"], [])
        warning_codes = {item["code"] for item in result["review_warnings"]}
        self.assertTrue(
            {
                "ACTIVE_COMPETITION_ELIGIBILITY",
                "TRANSFER_FEE_UNRESOLVED",
                "DESTINATION_TEAM_PENDING",
                "SOURCE_CLUB_RESPONSE_PENDING",
                "PLAYER_CONSENT_PENDING",
            }.issubset(warning_codes)
        )
        capability_codes = {item["code"] for item in result["capability_notes"]}
        self.assertEqual(
            capability_codes,
            {
                "TRANSFER_WINDOW_RULE_ENGINE_UNAVAILABLE",
                "TRAINING_COMPENSATION_CHECK_UNAVAILABLE",
                "PAYMENT_SETTLEMENT_CHECK_UNAVAILABLE",
                "CROSS_BORDER_CLEARANCE_UNAVAILABLE",
                "CONTRACT_DISPUTE_CHECK_UNAVAILABLE",
            },
        )

    def test_submission_stores_validation_revision_timestamp_and_initial_state(self):
        transfer = self._draft()
        submitted = submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        self.assertEqual(
            submitted.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        self.assertEqual(submitted.submission_revision, 1)
        self.assertIsNotNone(submitted.submitted_at)
        self.assertIn("review_warnings", submitted.automatic_validation)
        actions = set(UnionAuditEvent.objects.values_list("action", flat=True))
        self.assertIn("union_player_transfer.validation_completed", actions)
        self.assertIn("union_player_transfer.submitted", actions)
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

    def test_blocked_submission_preserves_draft_and_revision(self):
        transfer = self._draft(documents=[])
        with self.assertRaises(TransferSubmissionValidationError) as context:
            submit_player_transfer(
                transfer_id=transfer.id,
                actor=self.destination_actor,
            )
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.DRAFT)
        self.assertEqual(transfer.submission_revision, 0)
        self.assertIsNone(transfer.submitted_at)
        self.assertTrue(transfer.automatic_validation["blocking_errors"])
        self.assertTrue(context.exception.automatic_validation["blocking_errors"])

    def test_source_club_acknowledges_before_consent(self):
        transfer = self._submitted()
        updated = record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=(UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED),
            response="Registration details acknowledged.",
        )
        self.assertEqual(
            updated.source_club_response_status,
            UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
        )
        self.assertEqual(
            updated.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )

    def test_source_club_objection_requires_reason_and_does_not_reject(self):
        transfer = self._submitted()
        with self.assertRaises(ValidationError):
            record_source_club_transfer_response(
                transfer_id=transfer.id,
                actor=self.source_actor,
                response_status=(UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED),
                response=" ",
            )
        objected = record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
            response="Contract settlement remains disputed.",
        )
        self.assertEqual(
            objected.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        self.assertNotEqual(objected.status, UnionPlayerTransfer.Status.REJECTED)
        with self.assertRaises(ValidationError):
            record_source_club_transfer_response(
                transfer_id=transfer.id,
                actor=self.destination_actor,
                response_status=(
                    UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED
                ),
                response="Impersonated response.",
            )

    def test_linked_player_consents_but_unrelated_and_club_actors_cannot(self):
        transfer = self._submitted()
        for actor in (self.outside_actor, self.destination_actor, self.source_actor):
            with self.subTest(actor=actor.email):
                with self.assertRaises(ValidationError):
                    record_player_transfer_consent(
                        transfer_id=transfer.id,
                        actor=actor,
                        consent_method="PORTAL",
                    )
        consented = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.player_user,
            consent_method="PLAYER_PORTAL",
        )
        self.assertEqual(
            consented.player_consent_status,
            UnionPlayerTransfer.PlayerConsentStatus.CONSENTED,
        )
        self.assertEqual(
            consented.status,
            UnionPlayerTransfer.Status.SOURCE_CLUB_RESPONSE_REQUIRED,
        )

    def test_union_officer_records_verified_offline_consent(self):
        transfer = self._submitted()
        with self.assertRaises(ValidationError):
            record_player_transfer_consent(
                transfer_id=transfer.id,
                actor=self.union_officer,
                membership=self.officer_membership,
                consent_method="VERIFIED_OFFLINE",
            )
        consented = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.union_officer,
            membership=self.officer_membership,
            consent_method="VERIFIED_OFFLINE",
            evidence_reference="consent-record-42",
        )
        self.assertEqual(
            consented.player_consent_recorded_by,
            self.union_officer,
        )

    def test_prerequisites_progress_in_either_order_and_audit_once(self):
        first = self._submitted()
        record_player_transfer_consent(
            transfer_id=first.id,
            actor=self.player_user,
            consent_method="PORTAL",
        )
        completed = record_source_club_transfer_response(
            transfer_id=first.id,
            actor=self.source_actor,
            response_status=(UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED),
            response="Acknowledged.",
        )
        self.assertEqual(
            completed.status,
            UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action="union_player_transfer.prerequisites_completed",
                target_id=first.id,
            ).count(),
            1,
        )

        completed.status = UnionPlayerTransfer.Status.CANCELLED
        completed.save(update_fields=["status"])
        second = self._submitted()
        record_source_club_transfer_response(
            transfer_id=second.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
            response="Union review requested.",
        )
        second = record_player_transfer_consent(
            transfer_id=second.id,
            actor=self.player_user,
            consent_method="PORTAL",
        )
        self.assertEqual(
            second.status,
            UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )

    def test_player_decline_cancels_without_moving_authority(self):
        transfer = self._submitted()
        declined = decline_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.player_user,
            reason="Player declined the proposed move.",
        )
        self.assertEqual(declined.status, UnionPlayerTransfer.Status.CANCELLED)
        self.assertEqual(
            declined.player_consent_status,
            UnionPlayerTransfer.PlayerConsentStatus.DECLINED,
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
        actions = list(
            UnionAuditEvent.objects.filter(target_id=transfer.id).values_list(
                "action",
                flat=True,
            )
        )
        self.assertEqual(actions.count("union_player_transfer.cancelled"), 1)

    def test_destination_cancellation_boundaries_and_no_hard_delete(self):
        draft = self._draft()
        with self.assertRaises(ValidationError):
            cancel_player_transfer_request(
                transfer_id=draft.id,
                actor=self.destination_actor,
                reason=" ",
            )
        cancelled = cancel_player_transfer_request(
            transfer_id=draft.id,
            actor=self.destination_actor,
            reason="Destination Club withdrew its request.",
        )
        self.assertEqual(cancelled.status, UnionPlayerTransfer.Status.CANCELLED)
        self.assertTrue(UnionPlayerTransfer.objects.filter(pk=draft.id).exists())
        with self.assertRaises(ValidationError):
            record_player_transfer_consent(
                transfer_id=draft.id,
                actor=self.player_user,
                consent_method="PORTAL",
            )

        under_review = self._submitted()
        record_player_transfer_consent(
            transfer_id=under_review.id,
            actor=self.player_user,
            consent_method="PORTAL",
        )
        record_source_club_transfer_response(
            transfer_id=under_review.id,
            actor=self.source_actor,
            response_status=(UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED),
            response="Acknowledged.",
        )
        with self.assertRaises(ValidationError):
            cancel_player_transfer_request(
                transfer_id=under_review.id,
                actor=self.destination_actor,
                reason="Too late.",
            )

    def test_notifications_are_post_commit_and_actor_is_not_notified(self):
        transfer = self._draft()
        with self.captureOnCommitCallbacks(execute=True):
            submitted = submit_player_transfer(
                transfer_id=transfer.id,
                actor=self.destination_actor,
            )
        self.assertEqual(
            Notification.objects.filter(
                user__in=[self.player_user, self.source_actor]
            ).count(),
            2,
        )
        self.assertFalse(
            Notification.objects.filter(user=self.destination_actor).exists()
        )
        with self.captureOnCommitCallbacks(execute=True):
            record_source_club_transfer_response(
                transfer_id=submitted.id,
                actor=self.source_actor,
                response_status=(
                    UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED
                ),
                response="Acknowledged.",
            )
        self.assertTrue(
            Notification.objects.filter(user=self.destination_actor).exists()
        )
        before = Notification.objects.count()
        with self.captureOnCommitCallbacks(execute=True):
            record_player_transfer_consent(
                transfer_id=submitted.id,
                actor=self.player_user,
                consent_method="PORTAL",
            )
        self.assertGreater(Notification.objects.count(), before)

    def test_notification_failure_does_not_roll_back_or_leak_audit_evidence(self):
        transfer = self._draft()
        with patch(
            "dashboards.union_player_transfer_services.create_in_app_notification",
            side_effect=RuntimeError("notification unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                submitted = submit_player_transfer(
                    transfer_id=transfer.id,
                    actor=self.destination_actor,
                )
        submitted.refresh_from_db()
        self.assertEqual(
            submitted.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        private_values = {
            "transfer-document-reference",
            "consent-record-42",
            "Contract settlement remains disputed.",
        }
        for metadata in UnionAuditEvent.objects.filter(
            target_id=transfer.id
        ).values_list("metadata", flat=True):
            rendered = str(metadata)
            for private_value in private_values:
                self.assertNotIn(private_value, rendered)

    def test_changed_terms_reset_stale_prerequisite_evidence_but_noop_does_not(self):
        transfer = self._submitted()
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
            response="Acknowledged.",
        )
        transfer = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.player_user,
            consent_method="PORTAL",
        )
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.change_request_reason = "Update the effective date."
        transfer.save(update_fields=["status", "change_request_reason"])

        unchanged = update_player_transfer_draft(
            transfer_id=transfer.id,
            actor=self.destination_actor,
            updates={"effective_on": transfer.effective_on},
        )
        self.assertEqual(
            unchanged.source_club_response_status,
            UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
        )
        self.assertEqual(
            unchanged.player_consent_status,
            UnionPlayerTransfer.PlayerConsentStatus.CONSENTED,
        )

        changed = update_player_transfer_draft(
            transfer_id=transfer.id,
            actor=self.destination_actor,
            updates={"effective_on": date(2026, 8, 1)},
        )
        self.assertEqual(
            changed.source_club_response_status,
            UnionPlayerTransfer.SourceClubResponseStatus.PENDING,
        )
        self.assertEqual(
            changed.player_consent_status,
            UnionPlayerTransfer.PlayerConsentStatus.PENDING,
        )
        self.assertIsNone(changed.source_club_response_at)
        self.assertIsNone(changed.source_club_responded_by)
        self.assertIsNone(changed.player_consented_at)
        self.assertIsNone(changed.player_consent_recorded_by)
        metadata = (
            UnionAuditEvent.objects.filter(
                action="union_player_transfer.draft_updated",
                target_id=transfer.id,
            )
            .latest("id")
            .metadata
        )
        self.assertTrue(metadata["prerequisite_evidence_reset"])

    def test_destination_club_resubmits_and_preserves_original_submission_time(self):
        transfer = self._submitted()
        original_submitted_at = transfer.submitted_at
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.change_request_reason = "Refresh the transfer documents."
        transfer.save(update_fields=["status", "change_request_reason"])

        resubmitted = resubmit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        self.assertEqual(
            resubmitted.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        self.assertEqual(resubmitted.submitted_at, original_submitted_at)
        self.assertEqual(resubmitted.submission_revision, 2)
        self.assertIsNotNone(resubmitted.last_resubmitted_at)
        self.assertEqual(resubmitted.change_request_reason, "")
        actions = UnionAuditEvent.objects.filter(
            target_id=transfer.id,
        ).values_list("action", flat=True)
        self.assertIn("union_player_transfer.resubmitted", actions)

    def test_blocked_resubmission_preserves_changes_requested_evidence(self):
        transfer = self._submitted()
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.documents = []
        transfer.change_request_reason = "Provide documents."
        transfer.save(update_fields=["status", "documents", "change_request_reason"])
        original_submitted_at = transfer.submitted_at

        with self.assertRaises(TransferSubmissionValidationError):
            resubmit_player_transfer(
                transfer_id=transfer.id,
                actor=self.destination_actor,
            )
        transfer.refresh_from_db()
        self.assertEqual(
            transfer.status,
            UnionPlayerTransfer.Status.CHANGES_REQUESTED,
        )
        self.assertEqual(transfer.submission_revision, 1)
        self.assertEqual(transfer.submitted_at, original_submitted_at)
        self.assertIsNone(transfer.last_resubmitted_at)
        self.assertTrue(transfer.automatic_validation["blocking_errors"])

    def test_resubmission_derives_review_state_from_retained_evidence_once(self):
        transfer = self._submitted()
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
            response="Acknowledged.",
        )
        transfer = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=self.player_user,
            consent_method="PORTAL",
        )
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.change_request_reason = "Clarify without changing terms."
        transfer.save(update_fields=["status", "change_request_reason"])

        resubmitted = resubmit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        self.assertEqual(
            resubmitted.status,
            UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action="union_player_transfer.prerequisites_completed",
                target_id=transfer.id,
            ).count(),
            1,
        )
