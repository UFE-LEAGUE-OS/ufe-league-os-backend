from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
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
    process_due_player_transfer_activations,
)
from .union_player_transfer_return_services import return_loaned_player_to_source
from .union_player_transfer_review_services import approve_player_transfer_decision
from .union_player_transfer_services import (
    create_player_transfer_draft,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    submit_player_transfer,
)


class UnionPlayerTransferActivationServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.union = Union.objects.create(
            name="Activation Union",
            slug="activation-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Activation Workspace",
            slug="activation-workspace",
            acronym="AW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Activation League",
            slug="activation-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name=str(self.today.year),
            slug=f"activation-{self.today.year}",
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=240),
        )
        self.destination_actor = self._user("destination", User.Role.CLUB_ADMIN)
        self.source_actor = self._user("source", User.Role.CLUB_ADMIN)
        self.reviewer = self._user("reviewer", User.Role.FAN)
        self.source_club = self._club("Source", self.source_actor)
        self.destination_club = self._club("Destination", self.destination_actor)
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Activation Source Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Activation Destination Team",
        )
        for club in (self.source_club, self.destination_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Activation Cup",
            slug="activation-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Activation Competition",
            slug="activation-competition",
            season=str(self.today.year),
            season_record=self.season,
        )
        self.edition = CompetitionEdition.objects.create(
            identity=self.identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.ACTIVE,
        )
        self.membership = UnionWorkspaceMembership.objects.create(
            user=self.reviewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.REGISTRAR,
        )
        (
            self.player_user,
            self.player,
            self.registration,
            self.eligibility,
        ) = self._player_case("primary")

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin):
        club = Club.objects.create(
            name=f"{prefix} Activation Club",
            slug=f"{prefix.lower()}-activation-club",
            admin=admin,
        )
        ClubAdminScope.objects.create(
            user=admin,
            club=club,
            role=ClubAdminScope.Role.CHAIRMAN,
        )
        return club

    def _player_case(self, suffix):
        player_user = self._user(f"player-{suffix}", User.Role.FAN)
        player = UnionPlayer.objects.create(
            union=self.union,
            user=player_user,
            union_player_number=f"AU-P{UnionPlayer.objects.count() + 1:06d}",
            first_name="Activation",
            last_name=suffix.title(),
            date_of_birth=self.today - timedelta(days=9000),
            nationality="Ugandan",
            identity_reference=f"PRIVATE-IDENTITY-{suffix}",
            status=UnionPlayer.Status.APPROVED,
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
            effective_to=self.today + timedelta(days=180),
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

    def _under_review(
        self,
        *,
        transfer_type="PERMANENT",
        effective_on=None,
        player_user=None,
        registration=None,
    ):
        registration = registration or self.registration
        player_user = player_user or self.player_user
        effective_on = effective_on or self.today
        transfer = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=effective_on,
            transfer_type=transfer_type,
            loan_end_on=(
                effective_on + timedelta(days=30) if transfer_type == "LOAN" else None
            ),
            documents=["PRIVATE-ACTIVATION-DOCUMENT"],
            fee_status="PAID",
        )
        transfer = submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
            response="PRIVATE-SOURCE-RESPONSE",
        )
        return record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=player_user,
            consent_method="PLAYER_PORTAL",
        )

    def _approve(self, transfer):
        return approve_player_transfer_decision(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Approved for maintained activation.",
        )

    def _scheduled(
        self,
        *,
        transfer_type="PERMANENT",
        days=2,
        player_user=None,
        registration=None,
    ):
        transfer = self._under_review(
            transfer_type=transfer_type,
            effective_on=self.today + timedelta(days=days),
            player_user=player_user,
            registration=registration,
        )
        return self._approve(transfer)["transfer"]

    def test_future_permanent_free_and_loan_approvals_are_scheduled(self):
        for index, transfer_type in enumerate(("PERMANENT", "FREE_TRANSFER", "LOAN")):
            with self.subTest(transfer_type=transfer_type):
                if index:
                    player_user, _, registration, _ = self._player_case(
                        f"scheduled-{index}"
                    )
                else:
                    player_user, registration = self.player_user, self.registration
                transfer = self._scheduled(
                    transfer_type=transfer_type,
                    player_user=player_user,
                    registration=registration,
                )
                self.assertEqual(transfer.status, UnionPlayerTransfer.Status.APPROVED)
                self.assertIsNone(transfer.destination_registration)
                self.assertIsNone(transfer.activated_at)

    def test_future_approval_preserves_registration_and_eligibility(self):
        transfer = self._scheduled()
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
        self.assertFalse(
            UnionPlayerCompetitionEligibility.objects.filter(
                source_transfer=transfer
            ).exists()
        )

    def test_activation_plan_is_deterministic_and_private_evidence_free(self):
        transfer = self._scheduled(transfer_type="LOAN")
        plan = transfer.activation_plan
        self.assertEqual(plan["version"], 1)
        self.assertEqual(plan["affected_eligibility_ids"], [self.eligibility.id])
        self.assertEqual(plan["competition_identity_ids"], [self.identity.id])
        self.assertEqual(plan["competition_edition_ids"], [self.edition.id])
        self.assertEqual(
            plan["source_registration_original_effective_to"],
            self.registration.effective_to.isoformat(),
        )
        rendered = str(plan)
        for private_value in (
            "PRIVATE-ACTIVATION-DOCUMENT",
            "PRIVATE-SOURCE-RESPONSE",
            "PRIVATE-IDENTITY-primary",
        ):
            self.assertNotIn(private_value, rendered)

    def test_scheduled_approval_replay_is_idempotent(self):
        transfer = self._scheduled()
        plan = dict(transfer.activation_plan)
        audit_count = UnionAuditEvent.objects.filter(
            action__in={
                "union_player_transfer.approved",
                "union_player_transfer.activation_scheduled",
            },
            target_id=transfer.id,
        ).count()
        replay = self._approve(transfer)
        transfer.refresh_from_db()
        self.assertTrue(replay["idempotent_replay"])
        self.assertTrue(replay["activation_scheduled"])
        self.assertEqual(transfer.activation_plan, plan)
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action__in={
                    "union_player_transfer.approved",
                    "union_player_transfer.activation_scheduled",
                },
                target_id=transfer.id,
            ).count(),
            audit_count,
        )

    def test_current_permanent_and_free_transfers_activate_immediately(self):
        for index, transfer_type in enumerate(("PERMANENT", "FREE_TRANSFER")):
            with self.subTest(transfer_type=transfer_type):
                if index:
                    player_user, _, registration, _ = self._player_case("free")
                else:
                    player_user, registration = self.player_user, self.registration
                transfer = self._under_review(
                    transfer_type=transfer_type,
                    player_user=player_user,
                    registration=registration,
                )
                result = self._approve(transfer)
                self.assertFalse(result["activation_scheduled"])
                self.assertEqual(
                    result["transfer"].status,
                    UnionPlayerTransfer.Status.COMPLETED,
                )

    def test_immediate_permanent_history_and_eligibility_contract_is_preserved(self):
        original_expiry = self.registration.effective_to
        transfer = self._under_review()
        result = self._approve(transfer)
        destination = result["destination_registration"]
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.TRANSFERRED,
        )
        self.assertEqual(
            self.registration.effective_to,
            transfer.effective_on - timedelta(days=1),
        )
        self.assertEqual(destination.effective_to, original_expiry)
        self.assertEqual(destination.predecessor, self.registration)
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        )
        self.assertEqual(
            result["destination_eligibilities"][0].status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )

    def test_immediate_activation_replay_is_idempotent(self):
        transfer = self._under_review()
        first = self._approve(transfer)
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        replay = self._approve(transfer)
        self.assertTrue(replay["idempotent_replay"])
        self.assertFalse(replay["activation_scheduled"])
        self.assertEqual(
            replay["destination_registration"],
            first["destination_registration"],
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )

    def test_loan_date_validation_rejects_missing_order_and_finite_expiry(self):
        values = [
            {"loan_end_on": None},
            {"loan_end_on": self.today},
            {"loan_end_on": self.registration.effective_to},
        ]
        for overrides in values:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    create_player_transfer_draft(
                        actor=self.destination_actor,
                        workspace=self.workspace,
                        source_registration=self.registration,
                        destination_club=self.destination_club,
                        destination_team=self.destination_team,
                        effective_on=self.today,
                        transfer_type="LOAN",
                        documents=["reference"],
                        **overrides,
                    )

    def test_open_ended_and_shorter_finite_registrations_support_loans(self):
        self.registration.effective_to = None
        self.registration.save(update_fields=["effective_to"])
        open_ended = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=self.registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=self.today,
            transfer_type="LOAN",
            loan_end_on=self.today + timedelta(days=60),
            documents=["reference"],
        )
        self.assertEqual(open_ended.transfer_type, "LOAN")
        open_ended.status = UnionPlayerTransfer.Status.CANCELLED
        open_ended.save(update_fields=["status"])
        self.registration.effective_to = self.today + timedelta(days=180)
        self.registration.save(update_fields=["effective_to"])
        finite = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=self.registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=self.today,
            transfer_type="LOAN",
            loan_end_on=self.today + timedelta(days=30),
            documents=["reference"],
        )
        self.assertEqual(finite.loan_end_on, self.today + timedelta(days=30))

    def test_due_loan_activation_creates_bounded_destination_leg(self):
        transfer = self._under_review(transfer_type="LOAN")
        result = self._approve(transfer)
        destination = result["destination_registration"]
        self.registration.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        )
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.SUSPENDED,
        )
        self.assertEqual(
            self.registration.effective_to,
            transfer.effective_on - timedelta(days=1),
        )
        self.assertEqual(destination.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(destination.registration_type, "LOAN")
        self.assertEqual(destination.effective_to, transfer.loan_end_on)
        self.assertEqual(destination.predecessor, self.registration)
        self.assertIsNone(result["transfer"].completed_at)
        self.assertIsNotNone(result["transfer"].activated_at)
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)
        self.assertEqual(result["transfer"].return_plan["version"], 1)
        self.assertEqual(
            result["transfer"].return_plan["destination_registration_id"],
            destination.id,
        )
        self.assertEqual(
            result["transfer"].return_plan["destination_eligibility_ids"],
            [item.id for item in result["destination_eligibilities"]],
        )

    def test_loan_activation_closes_and_recreates_eligibility_as_pending(self):
        transfer = self._under_review(transfer_type="LOAN")
        result = self._approve(transfer)
        self.eligibility.refresh_from_db()
        destination = result["destination_eligibilities"][0]
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        )
        self.assertEqual(
            destination.status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )
        self.assertEqual(destination.source_transfer, transfer)
        self.assertIsNone(destination.reviewed_by)
        self.assertIsNone(destination.eligible_from)
        self.assertIsNone(destination.eligible_until)

    def test_loan_activation_replay_is_idempotent(self):
        transfer = self._under_review(transfer_type="LOAN")
        first = self._approve(transfer)
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        replay = activate_approved_player_transfer(transfer_id=transfer.id)
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

    def test_activation_replay_routes_completed_loan_return(self):
        transfer = self._under_review(transfer_type="LOAN")
        first = self._approve(transfer)
        returned = return_loaned_player_to_source(
            transfer_id=transfer.id,
            as_of=transfer.loan_end_on + timedelta(days=1),
        )
        replay = activate_approved_player_transfer(transfer_id=transfer.id)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["return_registration"],
            returned["return_registration"],
        )
        self.assertEqual(
            replay["destination_registration"],
            first["destination_registration"],
        )

    def test_transfer_cannot_activate_before_effective_date(self):
        transfer = self._scheduled()
        with self.assertRaisesMessage(
            ValidationError,
            "Transfer is not due for activation.",
        ):
            activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=self.today,
            )

    def test_missing_activation_plan_blocks_without_mutation(self):
        transfer = self._scheduled()
        transfer.activation_plan = {}
        transfer.save(update_fields=["activation_plan"])
        with self.assertRaises(ValidationError):
            activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=transfer.effective_on,
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

    def test_changed_destination_club_or_team_blocks_activation(self):
        other_admin = self._user("other-admin", User.Role.CLUB_ADMIN)
        other_club = self._club("Other", other_admin)
        ClubAffiliation.objects.create(
            workspace=self.workspace,
            club=other_club,
            status=ClubAffiliation.Status.ACTIVE,
        )
        other_team = Team.objects.create(club=self.destination_club, name="Other Team")
        for field, value in (
            ("destination_club", other_club),
            ("destination_team", other_team),
        ):
            with self.subTest(field=field):
                transfer = self._scheduled()
                setattr(transfer, field, value)
                transfer.save(update_fields=[field])
                with self.assertRaises(ValidationError):
                    activate_approved_player_transfer(
                        transfer_id=transfer.id,
                        as_of=transfer.effective_on,
                    )
                transfer.status = UnionPlayerTransfer.Status.CANCELLED
                transfer.save(update_fields=["status"])

    def test_changed_source_registration_blocks_activation(self):
        transfer = self._scheduled()
        replacement = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=self.player,
            club=self.source_club,
            status=UnionPlayerRegistration.Status.SUSPENDED,
            effective_from=self.today - timedelta(days=30),
        )
        transfer.source_registration = replacement
        transfer.save(update_fields=["source_registration"])
        with self.assertRaises(ValidationError):
            activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=transfer.effective_on,
            )

    def test_conflicting_active_registration_blocks_activation_atomically(self):
        transfer = self._scheduled()
        other_union = Union.objects.create(name="Other Union", slug="activation-other")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other Activation Workspace",
            slug="other-activation-workspace",
            acronym="OAW",
            sport="Football",
        )
        UnionPlayerRegistration.objects.create(
            workspace=other_workspace,
            player=self.player,
            club=self.destination_club,
            status=UnionPlayerRegistration.Status.ACTIVE,
            effective_from=self.today,
        )
        with self.assertRaises(ValidationError):
            activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=transfer.effective_on,
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

    def test_changed_eligibility_set_blocks_activation_atomically(self):
        transfer = self._scheduled()
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Late Cup",
            slug="late-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Late Competition",
            slug="late-competition",
            season=str(self.today.year),
            season_record=self.season,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.ACTIVE,
        )
        late = UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=identity,
            competition_edition=edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.PENDING,
        )
        with self.assertRaises(ValidationError):
            activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=transfer.effective_on,
            )
        self.registration.refresh_from_db()
        self.eligibility.refresh_from_db()
        late.refresh_from_db()
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self.assertEqual(
            self.eligibility.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        self.assertEqual(
            late.status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )

    def test_processor_activates_due_transfers_and_skips_future(self):
        first = self._scheduled(days=1)
        player_user, _, registration, _ = self._player_case("processor-second")
        second = self._scheduled(
            days=1,
            player_user=player_user,
            registration=registration,
        )
        player_user, _, registration, _ = self._player_case("processor-future")
        future = self._scheduled(
            days=2,
            player_user=player_user,
            registration=registration,
        )
        result = process_due_player_transfer_activations(
            as_of=self.today + timedelta(days=1)
        )
        self.assertEqual(result["due_count"], 2)
        self.assertEqual(result["activated_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["activated_transfer_ids"], [first.id, second.id])
        future.refresh_from_db()
        self.assertEqual(future.status, UnionPlayerTransfer.Status.APPROVED)

    def test_processor_records_failure_and_continues(self):
        failed = self._scheduled(days=1)
        failed.activation_plan = {}
        failed.save(update_fields=["activation_plan"])
        player_user, _, registration, _ = self._player_case("processor-valid")
        valid = self._scheduled(
            days=1,
            player_user=player_user,
            registration=registration,
        )
        result = process_due_player_transfer_activations(
            as_of=self.today + timedelta(days=1)
        )
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["activated_count"], 1)
        self.assertEqual(result["activated_transfer_ids"], [valid.id])
        self.assertEqual(result["failures"][0]["transfer_id"], failed.id)
        failed.refresh_from_db()
        self.assertEqual(failed.status, UnionPlayerTransfer.Status.APPROVED)

    def test_processor_positive_limit_is_enforced(self):
        first = self._scheduled(days=1)
        player_user, _, registration, _ = self._player_case("limited")
        second = self._scheduled(
            days=1,
            player_user=player_user,
            registration=registration,
        )
        result = process_due_player_transfer_activations(
            as_of=self.today + timedelta(days=1),
            limit=1,
        )
        self.assertEqual(result["due_count"], 2)
        self.assertEqual(result["activated_transfer_ids"], [first.id])
        second.refresh_from_db()
        self.assertEqual(second.status, UnionPlayerTransfer.Status.APPROVED)
        with self.assertRaises(ValidationError):
            process_due_player_transfer_activations(limit=0)

    def test_dry_run_command_changes_no_records(self):
        transfer = self._scheduled(days=1)
        output = StringIO()
        call_command(
            "process_scheduled_player_transfers",
            as_of=transfer.effective_on.isoformat(),
            dry_run=True,
            stdout=output,
        )
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.APPROVED)
        self.assertIn(str(transfer.id), output.getvalue())

    def test_command_activates_due_transfers_and_repeats_without_duplicates(self):
        transfer = self._scheduled(days=1)
        args = {
            "as_of": transfer.effective_on.isoformat(),
            "stdout": StringIO(),
        }
        call_command("process_scheduled_player_transfers", **args)
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        call_command(
            "process_scheduled_player_transfers",
            as_of=transfer.effective_on.isoformat(),
            stdout=StringIO(),
        )
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.COMPLETED)
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )

    def test_scheduled_and_activation_audits_are_written_once(self):
        transfer = self._scheduled(days=1, transfer_type="LOAN")
        activate_approved_player_transfer(
            transfer_id=transfer.id,
            as_of=transfer.effective_on,
        )
        activate_approved_player_transfer(
            transfer_id=transfer.id,
            as_of=transfer.effective_on,
        )
        for action in (
            "union_player_transfer.approved",
            "union_player_transfer.activation_scheduled",
            "union_player_transfer.activated",
            "union_player_transfer.loan_started",
        ):
            self.assertEqual(
                UnionAuditEvent.objects.filter(
                    action=action,
                    target_id=transfer.id,
                ).count(),
                1,
            )

    def test_scheduled_approval_and_activation_notifications_are_post_commit(self):
        transfer = self._under_review(effective_on=self.today + timedelta(days=1))
        with self.captureOnCommitCallbacks(execute=True):
            scheduled = self._approve(transfer)["transfer"]
        scheduled_notifications = Notification.objects.count()
        self.assertGreater(scheduled_notifications, 0)
        with self.captureOnCommitCallbacks(execute=True):
            activate_approved_player_transfer(
                transfer_id=scheduled.id,
                as_of=scheduled.effective_on,
            )
        self.assertGreater(Notification.objects.count(), scheduled_notifications)
        self.assertFalse(Notification.objects.filter(user=self.reviewer).exists())

    def test_notification_failure_does_not_roll_back_activation(self):
        transfer = self._scheduled(days=1)
        with patch(
            (
                "dashboards.union_player_transfer_review_services."
                "create_in_app_notification"
            ),
            side_effect=RuntimeError("notification unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = activate_approved_player_transfer(
                    transfer_id=transfer.id,
                    as_of=transfer.effective_on,
                )
        self.assertEqual(
            result["transfer"].status,
            UnionPlayerTransfer.Status.COMPLETED,
        )
        self.assertEqual(
            result["destination_registration"].status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
