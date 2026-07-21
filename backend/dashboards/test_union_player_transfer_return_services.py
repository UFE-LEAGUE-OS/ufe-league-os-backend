from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
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
from .union_player_transfer_activation_services import (
    activate_approved_player_transfer,
)
from .union_player_transfer_return_services import (
    process_due_player_loan_returns,
    return_loaned_player_to_source,
)
from .union_player_transfer_review_services import approve_player_transfer_decision
from .union_player_transfer_services import (
    create_player_transfer_draft,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    submit_player_transfer,
)


class UnionPlayerTransferReturnServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.union = Union.objects.create(
            name="Loan Return Union",
            slug="loan-return-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Loan Return Workspace",
            slug="loan-return-workspace",
            acronym="LRW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Loan Return League",
            slug="loan-return-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name=str(self.today.year),
            slug=f"loan-return-{self.today.year}",
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=365),
        )
        self.destination_actor = self._user("destination", User.Role.CLUB_ADMIN)
        self.source_actor = self._user("source", User.Role.CLUB_ADMIN)
        self.reviewer = self._user("reviewer", User.Role.FAN)
        self.source_club = self._club("Source", self.source_actor)
        self.destination_club = self._club("Destination", self.destination_actor)
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Loan Return Source Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Loan Return Destination Team",
        )
        for club in (self.source_club, self.destination_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.membership = UnionWorkspaceMembership.objects.create(
            user=self.reviewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.identity, self.edition = self._competition("primary")

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin):
        club = Club.objects.create(
            name=f"{prefix} Loan Return Club",
            slug=f"{prefix.lower()}-loan-return-club",
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
            name=f"Loan Return Cup {suffix}",
            slug=f"loan-return-cup-{suffix}",
        )
        competition = Competition.objects.create(
            league=self.league,
            name=f"Loan Return Competition {suffix}",
            slug=f"loan-return-competition-{suffix}",
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

    def _player_case(self, suffix, *, source_expiry="default"):
        player_user = self._user(f"player-{suffix}", User.Role.FAN)
        player = UnionPlayer.objects.create(
            union=self.union,
            user=player_user,
            union_player_number=f"LR-P{UnionPlayer.objects.count() + 1:06d}",
            first_name="Loan",
            last_name=suffix.title(),
            date_of_birth=self.today - timedelta(days=9000),
            nationality="Ugandan",
            identity_reference=f"PRIVATE-IDENTITY-{suffix}",
            status=UnionPlayer.Status.APPROVED,
        )
        effective_to = (
            self.today + timedelta(days=180)
            if source_expiry == "default"
            else source_expiry
        )
        registration = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player,
            club=self.source_club,
            team=self.source_team,
            season=self.season,
            status=UnionPlayerRegistration.Status.ACTIVE,
            registration_type="FIRST_REGISTRATION",
            effective_from=self.today - timedelta(days=120),
            effective_to=effective_to,
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )
        eligibility = UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=player,
            registration=registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=self.identity,
            competition_edition=self.edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
            warnings=[
                {
                    "code": "MAINTAINED_WARNING",
                    "field": "player",
                    "message": "Maintained warning.",
                    "severity": "WARNING",
                    "private_extra": "not copied",
                }
            ],
        )
        return player_user, player, registration, eligibility

    def _add_source_eligibility(self, registration, suffix, *, status=None):
        identity, edition = self._competition(suffix)
        return UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=registration.player,
            registration=registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=identity,
            competition_edition=edition,
            season=self.season,
            status=status or UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )

    def _activate(
        self,
        suffix="primary",
        *,
        source_expiry="default",
        transfer_type="LOAN",
        extra_source_eligibilities=0,
    ):
        player_user, player, registration, eligibility = self._player_case(
            suffix,
            source_expiry=source_expiry,
        )
        for index in range(extra_source_eligibilities):
            self._add_source_eligibility(registration, f"{suffix}-{index}")
        loan_end_on = (
            self.today + timedelta(days=30) if transfer_type == "LOAN" else None
        )
        transfer = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=self.today,
            transfer_type=transfer_type,
            loan_end_on=loan_end_on,
            documents=["PRIVATE-RETURN-DOCUMENT"],
            fee_status="PAID",
        )
        submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
            response="PRIVATE-SOURCE-OBJECTION",
        )
        record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=player_user,
            consent_method="PRIVATE-CONSENT-METHOD",
        )
        result = approve_player_transfer_decision(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Approved for maintained loan return.",
        )
        return {
            **result,
            "player_user": player_user,
            "player": player,
            "source_registration": registration,
            "source_eligibility": eligibility,
        }

    def _return(self, activated, *, as_of=None):
        transfer = activated["transfer"]
        return return_loaned_player_to_source(
            transfer_id=transfer.id,
            as_of=as_of or transfer.loan_end_on + timedelta(days=1),
        )

    def test_loan_activation_freezes_complete_private_safe_return_plan(self):
        activated = self._activate()
        transfer = activated["transfer"]
        destination = activated["destination_registration"]
        destination_eligibilities = activated["destination_eligibilities"]
        plan = transfer.return_plan
        self.assertEqual(plan["version"], 1)
        self.assertEqual(plan["workspace_id"], self.workspace.id)
        self.assertEqual(plan["player_id"], activated["player"].id)
        self.assertEqual(
            plan["source_registration_id"],
            activated["source_registration"].id,
        )
        self.assertEqual(plan["source_club_id"], self.source_club.id)
        self.assertEqual(plan["source_team_id"], self.source_team.id)
        self.assertEqual(plan["destination_registration_id"], destination.id)
        self.assertEqual(plan["destination_club_id"], self.destination_club.id)
        self.assertEqual(plan["destination_team_id"], self.destination_team.id)
        self.assertEqual(plan["loan_end_on"], transfer.loan_end_on.isoformat())
        self.assertEqual(
            plan["return_effective_on"],
            (transfer.loan_end_on + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(
            plan["destination_eligibility_ids"],
            [item.id for item in destination_eligibilities],
        )
        rendered = str(plan)
        for private_value in (
            "PRIVATE-RETURN-DOCUMENT",
            "PRIVATE-SOURCE-OBJECTION",
            "PRIVATE-CONSENT-METHOD",
            "PRIVATE-IDENTITY-primary",
        ):
            self.assertNotIn(private_value, rendered)

    def test_permanent_and_free_transfers_leave_return_plan_empty(self):
        for index, transfer_type in enumerate(("PERMANENT", "FREE_TRANSFER")):
            with self.subTest(transfer_type=transfer_type):
                activated = self._activate(
                    f"non-loan-{index}",
                    transfer_type=transfer_type,
                )
                self.assertEqual(activated["transfer"].return_plan, {})

    def test_active_loan_replay_verifies_frozen_return_plan(self):
        activated = self._activate()
        transfer = activated["transfer"]
        replay = activate_approved_player_transfer(transfer_id=transfer.id)
        self.assertTrue(replay["idempotent_replay"])
        transfer.return_plan = {**transfer.return_plan, "source_club_id": 999999}
        transfer.save(update_fields=["return_plan", "updated_at"])
        with self.assertRaisesMessage(
            ValidationError,
            "Active loan no longer matches its frozen return plan.",
        ):
            activate_approved_player_transfer(transfer_id=transfer.id)

    def test_return_is_due_only_after_the_final_loan_day(self):
        activated = self._activate()
        transfer = activated["transfer"]
        for as_of in (
            transfer.loan_end_on - timedelta(days=1),
            transfer.loan_end_on,
        ):
            with self.subTest(as_of=as_of):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Loan is not due for return.",
                ):
                    self._return(activated, as_of=as_of)
        result = self._return(
            activated,
            as_of=transfer.loan_end_on + timedelta(days=1),
        )
        self.assertEqual(
            result["transfer"].status, UnionPlayerTransfer.Status.COMPLETED
        )

    def test_open_ended_and_finite_source_expiry_are_restored(self):
        cases = (
            ("open", None),
            ("finite", self.today + timedelta(days=180)),
        )
        for suffix, expiry in cases:
            with self.subTest(expiry=expiry):
                activated = self._activate(suffix, source_expiry=expiry)
                returned = self._return(activated)
                self.assertEqual(returned["return_registration"].effective_to, expiry)

    def test_return_creates_authoritative_successor_and_preserves_history(self):
        activated = self._activate()
        transfer = activated["transfer"]
        source = activated["source_registration"]
        destination = activated["destination_registration"]
        original_expiry = transfer.source_registration_original_effective_to
        result = self._return(activated)
        transfer.refresh_from_db()
        source.refresh_from_db()
        destination.refresh_from_db()
        returned = result["return_registration"]
        activated["player"].refresh_from_db()
        self.assertEqual(source.status, UnionPlayerRegistration.Status.SUSPENDED)
        self.assertEqual(
            source.effective_to,
            transfer.effective_on - timedelta(days=1),
        )
        self.assertEqual(destination.status, UnionPlayerRegistration.Status.EXPIRED)
        self.assertEqual(destination.effective_to, transfer.loan_end_on)
        self.assertEqual(returned.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(returned.club, self.source_club)
        self.assertEqual(returned.team, self.source_team)
        self.assertEqual(
            returned.effective_from,
            transfer.loan_end_on + timedelta(days=1),
        )
        self.assertEqual(returned.effective_to, original_expiry)
        self.assertEqual(returned.predecessor, destination)
        self.assertEqual(returned.registration_type, "END_OF_LOAN")
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.COMPLETED)
        self.assertEqual(transfer.return_registration, returned)
        self.assertIsNotNone(transfer.returned_at)
        self.assertIsNotNone(transfer.completed_at)
        self.assertEqual(activated["player"].status, UnionPlayer.Status.APPROVED)

    def test_inactive_destination_affiliation_does_not_block_return(self):
        activated = self._activate()
        ClubAffiliation.objects.filter(
            workspace=self.workspace,
            club=self.destination_club,
        ).update(status=ClubAffiliation.Status.SUSPENDED)
        result = self._return(activated)
        self.assertEqual(
            result["transfer"].status, UnionPlayerTransfer.Status.COMPLETED
        )

    def test_inactive_source_affiliation_blocks_return(self):
        activated = self._activate()
        ClubAffiliation.objects.filter(
            workspace=self.workspace,
            club=self.source_club,
        ).update(status=ClubAffiliation.Status.SUSPENDED)
        with self.assertRaisesMessage(
            ValidationError,
            "Source Club requires an active workspace affiliation.",
        ):
            self._return(activated)
        activated["transfer"].refresh_from_db()
        self.assertEqual(
            activated["transfer"].status,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        )

    def test_nonterminal_destination_eligibilities_close_and_reapply(self):
        activated = self._activate("nonterminal", extra_source_eligibilities=2)
        destinations = activated["destination_eligibilities"]
        statuses = (
            UnionPlayerCompetitionEligibility.Status.PENDING,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
            UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        )
        for eligibility, status in zip(destinations, statuses, strict=True):
            eligibility.status = status
            eligibility.save(update_fields=["status", "updated_at"])
        result = self._return(activated)
        expected_closed = (
            UnionPlayerCompetitionEligibility.Status.CANCELLED,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        )
        for eligibility, expected in zip(destinations, expected_closed, strict=True):
            eligibility.refresh_from_db()
            self.assertEqual(eligibility.status, expected)
        returned = result["return_eligibilities"]
        self.assertEqual(len(returned), 3)
        self.assertEqual(
            {item.status for item in returned},
            {UnionPlayerCompetitionEligibility.Status.PENDING},
        )
        self.assertEqual(
            {item.source_loan_return_id for item in returned},
            {activated["transfer"].id},
        )
        self.assertEqual(
            {item.registration_id for item in returned},
            {result["return_registration"].id},
        )
        self.assertEqual(
            {item.competition_edition_id for item in returned},
            set(activated["transfer"].return_plan["competition_edition_ids"]),
        )

    def test_terminal_destination_eligibilities_are_preserved_and_reapply(self):
        activated = self._activate("terminal", extra_source_eligibilities=3)
        destinations = activated["destination_eligibilities"]
        terminal_statuses = (
            UnionPlayerCompetitionEligibility.Status.REJECTED,
            UnionPlayerCompetitionEligibility.Status.CANCELLED,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
            UnionPlayerCompetitionEligibility.Status.INELIGIBLE,
        )
        for eligibility, status in zip(destinations, terminal_statuses, strict=True):
            eligibility.status = status
            eligibility.save(update_fields=["status", "updated_at"])
        result = self._return(activated)
        for eligibility, expected in zip(
            destinations,
            terminal_statuses,
            strict=True,
        ):
            eligibility.refresh_from_db()
            self.assertEqual(eligibility.status, expected)
        self.assertEqual(len(result["return_eligibilities"]), 4)

    def test_return_eligibility_carries_only_sanitized_warnings(self):
        activated = self._activate()
        destination = activated["destination_eligibilities"][0]
        destination.status = UnionPlayerCompetitionEligibility.Status.ELIGIBLE
        destination.eligible_from = self.today
        destination.reviewed_by = self.reviewer
        destination.reviewed_at = timezone.now()
        destination.decision_reason = "PRIVATE DECISION"
        destination.restriction_reason = "PRIVATE RESTRICTION"
        destination.save()
        returned = self._return(activated)["return_eligibilities"][0]
        self.assertEqual(
            returned.warnings,
            [
                {
                    "code": "MAINTAINED_WARNING",
                    "field": "player",
                    "message": "Maintained warning.",
                    "severity": "WARNING",
                }
            ],
        )
        self.assertIsNone(returned.eligible_from)
        self.assertIsNone(returned.eligible_until)
        self.assertIsNone(returned.reviewed_by)
        self.assertIsNone(returned.reviewed_at)
        self.assertEqual(returned.decision_reason, "")
        self.assertEqual(returned.restriction_reason, "")

    def test_missing_return_plan_blocks_return(self):
        activated = self._activate()
        UnionPlayerTransfer.objects.filter(pk=activated["transfer"].id).update(
            return_plan={}
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Loan return plan is missing or unsupported.",
        ):
            self._return(activated)

    def test_changed_destination_registration_evidence_blocks_return(self):
        activated = self._activate()
        transfer = activated["transfer"]
        transfer.return_plan = {
            **transfer.return_plan,
            "destination_registration_id": transfer.destination_registration_id + 1,
        }
        transfer.save(update_fields=["return_plan", "updated_at"])
        with self.assertRaisesMessage(
            ValidationError,
            "Current loan evidence differs from the frozen return plan.",
        ):
            self._return(activated)

    def test_changed_original_source_evidence_blocks_return(self):
        activated = self._activate()
        source = activated["source_registration"]
        source.team = None
        source.save(update_fields=["team", "updated_at"])
        with self.assertRaisesMessage(
            ValidationError,
            "Current loan evidence differs from the frozen return plan.",
        ):
            self._return(activated)

    def test_conflicting_active_registration_blocks_return(self):
        activated = self._activate()
        other_workspace = UnionWorkspace.objects.create(
            name="Conflicting Workspace",
            slug="conflicting-workspace",
            acronym="CW",
            sport="Football",
        )
        UnionPlayerRegistration.objects.create(
            workspace=other_workspace,
            player=activated["player"],
            club=self.source_club,
            team=self.source_team,
            season=self.season,
            status=UnionPlayerRegistration.Status.ACTIVE,
            effective_from=self.today,
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Destination loan must be the only active row.",
        ):
            self._return(activated)

    def test_changed_destination_eligibility_set_blocks_return(self):
        activated = self._activate()
        identity, edition = self._competition("unexpected")
        UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=activated["player"],
            registration=activated["destination_registration"],
            source_transfer=activated["transfer"],
            club=self.destination_club,
            team=self.destination_team,
            competition_identity=identity,
            competition_edition=edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.PENDING,
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Current loan evidence differs from the frozen return plan.",
        ):
            self._return(activated)

    def test_failure_rolls_back_registration_eligibility_and_transfer_changes(self):
        activated = self._activate()
        transfer = activated["transfer"]
        source = activated["source_registration"]
        destination = activated["destination_registration"]
        source.refresh_from_db()
        destination.refresh_from_db()
        source_status = source.status
        destination_status = destination.status
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        registration_count = UnionPlayerRegistration.objects.count()
        with patch(
            "dashboards.union_player_transfer_return_services.log_union_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaisesMessage(RuntimeError, "audit unavailable"):
                self._return(activated)
        transfer.refresh_from_db()
        source.refresh_from_db()
        destination.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.LOAN_ACTIVE)
        self.assertIsNone(transfer.return_registration)
        self.assertEqual(source.status, source_status)
        self.assertEqual(destination.status, destination_status)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)

    def test_return_replay_is_idempotent(self):
        activated = self._activate()
        first = self._return(activated)
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        audit_count = UnionAuditEvent.objects.count()
        notification_count = Notification.objects.count()
        replay = self._return(activated)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["return_registration"].id,
            first["return_registration"].id,
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )
        self.assertEqual(UnionAuditEvent.objects.count(), audit_count)
        self.assertEqual(Notification.objects.count(), notification_count)

    def test_activation_replay_routes_completed_loan_return(self):
        activated = self._activate()
        returned = self._return(activated)
        replay = activate_approved_player_transfer(
            transfer_id=activated["transfer"].id,
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["return_registration"].id,
            returned["return_registration"].id,
        )

    def test_approval_replay_routes_completed_loan_return(self):
        activated = self._activate()
        returned = self._return(activated)
        replay = approve_player_transfer_decision(
            transfer_id=activated["transfer"].id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Replay completed loan.",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["return_registration"].id,
            returned["return_registration"].id,
        )

    def test_return_audit_events_are_once_and_privacy_safe(self):
        activated = self._activate()
        before = UnionAuditEvent.objects.count()
        self._return(activated)
        actions = {
            event.action for event in UnionAuditEvent.objects.order_by("id")[before:]
        }
        self.assertEqual(
            actions,
            {
                "union_player_transfer.loan_returned",
                "union_player_transfer.completed",
                "union_player_registration.loan_destination_expired",
                "union_player_registration.loan_return_created",
                "competition_eligibility.closed_for_loan_return",
                "competition_eligibility.pending_created_for_loan_return",
            },
        )
        rendered = str(
            list(
                UnionAuditEvent.objects.order_by("id")[before:].values_list(
                    "metadata",
                    flat=True,
                )
            )
        )
        for private_value in (
            "PRIVATE-RETURN-DOCUMENT",
            "PRIVATE-SOURCE-OBJECTION",
            "PRIVATE-CONSENT-METHOD",
            "PRIVATE-IDENTITY-primary",
            "Approved for maintained loan return.",
        ):
            self.assertNotIn(private_value, rendered)
        count = UnionAuditEvent.objects.count()
        self._return(activated)
        self.assertEqual(UnionAuditEvent.objects.count(), count)

    def test_return_notifications_execute_after_commit_and_exclude_reviewer(self):
        activated = self._activate()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self._return(activated)
        self.assertEqual(len(callbacks), 3)
        recipients = set(Notification.objects.values_list("user_id", flat=True))
        self.assertEqual(
            recipients,
            {
                self.destination_actor.id,
                self.source_actor.id,
                activated["player_user"].id,
            },
        )
        self.assertNotIn(self.reviewer.id, recipients)
        metadata = list(Notification.objects.values_list("metadata", flat=True))
        self.assertTrue(all("return_registration_id" in item for item in metadata))

    def test_notification_failure_does_not_roll_back_return(self):
        activated = self._activate()
        with patch(
            "dashboards.union_player_transfer_return_services."
            "create_in_app_notification",
            side_effect=RuntimeError("notification unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = self._return(activated)
        result["transfer"].refresh_from_db()
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.COMPLETED,
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_processor_returns_due_loans_skips_final_day_and_honours_limit(self):
        due_one = self._activate("processor-one")
        due_two = self._activate("processor-two")
        final_day = self._activate("processor-final")
        as_of = due_one["transfer"].loan_end_on + timedelta(days=1)
        final_day["transfer"].loan_end_on = as_of
        final_day["transfer"].return_plan = {
            **final_day["transfer"].return_plan,
            "loan_end_on": as_of.isoformat(),
            "return_effective_on": (as_of + timedelta(days=1)).isoformat(),
        }
        final_day["transfer"].save(
            update_fields=["loan_end_on", "return_plan", "updated_at"]
        )
        limited = process_due_player_loan_returns(as_of=as_of, limit=1)
        self.assertEqual(limited["due_count"], 2)
        self.assertEqual(limited["returned_count"], 1)
        remaining = process_due_player_loan_returns(as_of=as_of)
        self.assertEqual(remaining["due_count"], 1)
        self.assertEqual(remaining["returned_count"], 1)
        final_day["transfer"].refresh_from_db()
        self.assertEqual(
            final_day["transfer"].status,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        )
        self.assertEqual(
            set(limited["returned_transfer_ids"] + remaining["returned_transfer_ids"]),
            {due_one["transfer"].id, due_two["transfer"].id},
        )

    def test_processor_records_failure_and_continues(self):
        invalid = self._activate("processor-invalid")
        valid = self._activate("processor-valid")
        UnionPlayerTransfer.objects.filter(pk=invalid["transfer"].id).update(
            return_plan={}
        )
        as_of = valid["transfer"].loan_end_on + timedelta(days=1)
        result = process_due_player_loan_returns(as_of=as_of)
        self.assertEqual(result["due_count"], 2)
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(
            result["returned_transfer_ids"],
            [valid["transfer"].id],
        )
        self.assertEqual(result["failures"][0]["transfer_id"], invalid["transfer"].id)
        self.assertNotIn("PRIVATE", result["failures"][0]["error"])
        invalid["transfer"].refresh_from_db()
        self.assertEqual(
            invalid["transfer"].status,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        )

    def test_management_command_dry_run_normal_run_and_replay(self):
        activated = self._activate("command")
        transfer = activated["transfer"]
        as_of = transfer.loan_end_on + timedelta(days=1)
        dry_output = StringIO()
        call_command(
            "process_due_player_loan_returns",
            as_of=as_of.isoformat(),
            dry_run=True,
            stdout=dry_output,
        )
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.LOAN_ACTIVE)
        self.assertIn(str(transfer.id), dry_output.getvalue())
        self.assertIn(
            (transfer.loan_end_on + timedelta(days=1)).isoformat(),
            dry_output.getvalue(),
        )
        output = StringIO()
        call_command(
            "process_due_player_loan_returns",
            as_of=as_of.isoformat(),
            stdout=output,
        )
        self.assertIn("Returned: 1", output.getvalue())
        replay_output = StringIO()
        call_command(
            "process_due_player_loan_returns",
            as_of=as_of.isoformat(),
            stdout=replay_output,
        )
        self.assertIn("Returned: 0", replay_output.getvalue())
        with self.assertRaises(CommandError):
            call_command(
                "process_due_player_loan_returns",
                as_of="not-a-date",
            )
        with self.assertRaises(CommandError):
            call_command(
                "process_due_player_loan_returns",
                limit=0,
            )
