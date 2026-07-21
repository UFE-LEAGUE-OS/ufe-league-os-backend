from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Club, Notification, User
from teams.models import PlayerRegistration, Team

from .models import (
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    League,
    LeagueClubMembership,
    Season,
    Union,
    UnionAuditEvent,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_player_eligibility_services import (
    EligibilityValidationError,
    approve_player_competition_eligibility,
    cancel_player_competition_eligibility,
    create_pending_eligibilities_for_submission,
    expire_player_competition_eligibility,
    reinstate_player_competition_eligibility,
    reject_player_competition_eligibility,
    suspend_player_competition_eligibility,
    validate_player_competition_eligibility,
)
from .union_player_review_services import (
    approve_player_registration_submission,
)


class UnionPlayerEligibilityServiceTests(TestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Eligibility Union",
            slug="eligibility-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Eligibility Workspace",
            slug="eligibility-workspace",
            acronym="EW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Eligibility League",
            slug="eligibility-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026",
            slug="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.next_season = Season.objects.create(
            league=self.league,
            name="2027",
            slug="2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
        )
        self.reviewer = self._user("reviewer")
        self.submitter = self._user("submitter")
        self.membership = self._membership(
            self.reviewer,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.club = Club.objects.create(
            name="Eligibility Club",
            slug="eligibility-club",
            admin=self.submitter,
        )
        self.team = Team.objects.create(
            club=self.club,
            name="Eligibility First Team",
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.season,
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.next_season,
        )
        self.identity, self.edition = self._edition(
            "eligibility-cup",
            self.season,
        )
        self.player = self._player("EU-P000001")
        self.registration = self._registration()
        self.submission = self._submission()
        self.submission.requested_competition_editions.add(self.edition)

    def _user(self, prefix):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
        )

    def _membership(
        self,
        user,
        role,
        *,
        workspace=None,
        scope_restrictions=None,
        is_active=True,
    ):
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace or self.workspace,
            role=role,
            scope_restrictions=scope_restrictions or {},
            is_active=is_active,
        )

    def _player(self, number, *, union=None, player_status=None):
        return UnionPlayer.objects.create(
            union=union or self.union,
            union_player_number=number,
            first_name="Grace",
            last_name=number,
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=player_status or UnionPlayer.Status.APPROVED,
        )

    def _edition(self, slug, season, *, union=None, edition_status=None):
        target_union = union or self.union
        league = self.league
        if target_union != self.union:
            league = League.objects.create(
                union=target_union,
                name=f"{slug} League",
                slug=f"{slug}-league",
            )
        identity = CompetitionIdentity.objects.create(
            union=target_union,
            primary_league=league,
            name=f"{slug} Identity",
            slug=slug,
            default_eligibility_rules={"foreign_player_limit": 5},
        )
        competition = Competition.objects.create(
            league=league,
            name=f"{slug} Edition",
            slug=f"{slug}-edition",
            season=season.name,
            season_record=season,
            start_date=season.start_date,
            end_date=season.end_date,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=season,
            status=edition_status or CompetitionEdition.Status.REGISTRATION_OPEN,
            registration_closes_at=timezone.now() + timedelta(days=5),
            eligibility_rules={"minimum_age": 16},
        )
        return identity, edition

    def _registration(
        self,
        *,
        player=None,
        club=None,
        team=None,
        season=None,
        status_value=None,
        source_submission=None,
        effective_from=None,
    ):
        return UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player or self.player,
            club=club or self.club,
            team=team or self.team,
            season=season or self.season,
            source_registration=source_submission,
            status=status_value or UnionPlayerRegistration.Status.ACTIVE,
            registration_type=PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
            effective_from=effective_from or date(2026, 1, 1),
            effective_to=(season or self.season).end_date,
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )

    def _submission(
        self,
        *,
        player=None,
        season=None,
        submission_status=None,
        registration_type=None,
        registered_date=None,
    ):
        selected_season = season or self.season
        number = PlayerRegistration.objects.count() + 1
        return PlayerRegistration.objects.create(
            club=self.club,
            team=self.team,
            registration_number=f"ELIG-SUB-{number}",
            first_name="Grace",
            last_name=f"Applicant {number}",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            position="MID",
            registered_date=registered_date or selected_season.start_date,
            expiry_date=selected_season.end_date,
            union_workspace=self.workspace,
            union_player=player or self.player,
            season_record=selected_season,
            supporting_documents=["document-reference"],
            club_notes="Preserved Club note",
            submitted_by=self.submitter,
            submitted_at=timezone.now(),
            submission_revision=1,
            submission_status=(
                submission_status or PlayerRegistration.SubmissionStatus.APPROVED
            ),
            registration_type=(
                registration_type
                or PlayerRegistration.RegistrationType.FIRST_REGISTRATION
            ),
            status=PlayerRegistration.RegistrationStatus.ACTIVE,
            automatic_validation={
                "review_warnings": [
                    {
                        "code": "PLAYER_IDENTITY_PROVISIONAL",
                        "field": "union_player",
                        "message": "Identity was provisional at submission.",
                        "severity": "WARNING",
                    }
                ]
            },
        )

    def _create_pending(self, submission=None, registration=None):
        return create_pending_eligibilities_for_submission(
            submission=submission or self.submission,
            authoritative_registration=registration or self.registration,
            actor=self.reviewer,
            membership=self.membership,
        )

    def _eligibility(self):
        return self._create_pending()["eligibilities"][0]

    def _approve_eligibility(self, eligibility, **overrides):
        return approve_player_competition_eligibility(
            eligibility_id=eligibility.id,
            reviewer=overrides.get("reviewer", self.reviewer),
            membership=overrides.get("membership", self.membership),
            reason=overrides.get("reason", "All maintained checks passed."),
            eligible_from=overrides.get("eligible_from"),
            eligible_until=overrides.get("eligible_until"),
        )

    def test_pending_creation_is_linked_pending_audited_and_idempotent(self):
        first = self._create_pending()
        eligibility = first["eligibilities"][0]
        self.assertEqual(first["created_count"], 1)
        self.assertEqual(first["existing_count"], 0)
        self.assertFalse(first["idempotent_replay"])
        self.assertEqual(
            eligibility.status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )
        self.assertEqual(eligibility.source_submission, self.submission)
        self.assertEqual(eligibility.registration, self.registration)
        self.assertTrue(eligibility.warnings)
        self.assertFalse(
            UnionPlayerCompetitionEligibility.objects.filter(
                status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE
            ).exists()
        )
        second = self._create_pending()
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["existing_count"], 1)
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(second["eligibilities"][0].id, eligibility.id)
        self.assertEqual(UnionPlayerCompetitionEligibility.objects.count(), 1)
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action="competition_eligibility.pending_created"
            ).count(),
            1,
        )

    def test_no_requested_editions_creates_nothing(self):
        self.submission.requested_competition_editions.clear()
        result = self._create_pending()
        self.assertEqual(
            result,
            {
                "eligibilities": [],
                "created_count": 0,
                "existing_count": 0,
                "idempotent_replay": False,
            },
        )
        self.assertEqual(UnionPlayerCompetitionEligibility.objects.count(), 0)

    def test_pending_creation_rejects_wrong_workspace_and_season_editions(self):
        other_union = Union.objects.create(
            name="Other Eligibility Union",
            slug="other-eligibility-union",
        )
        other_season = Season.objects.create(
            league=League.objects.create(
                union=other_union,
                name="Other Eligibility League",
                slug="other-eligibility-league",
            ),
            name="2026",
            slug="other-2026",
        )
        _, other_edition = self._edition(
            "wrong-union-cup",
            other_season,
            union=other_union,
        )
        self.submission.requested_competition_editions.set([other_edition])
        with self.assertRaises(ValidationError):
            self._create_pending()

        _, next_edition = self._edition("wrong-season-cup", self.next_season)
        self.submission.requested_competition_editions.set([next_edition])
        with self.assertRaises(ValidationError):
            self._create_pending()

    def test_pending_creation_enforces_all_resource_scopes(self):
        restrictions = [
            {"club_ids": []},
            {
                "club_ids": [self.club.id],
                "competition_identity_ids": [],
            },
            {
                "club_ids": [self.club.id],
                "competition_identity_ids": [self.identity.id],
                "competition_edition_ids": [],
            },
        ]
        for scope_restrictions in restrictions:
            with self.subTest(scope_restrictions=scope_restrictions):
                self.membership.scope_restrictions = scope_restrictions
                self.membership.save(update_fields=["scope_restrictions"])
                with self.assertRaises(ValidationError):
                    self._create_pending()

    def test_first_registration_approval_creates_pending_eligibility(self):
        player = self._player(
            "EU-FIRST",
            player_status=UnionPlayer.Status.PROVISIONAL,
        )
        submission = self._submission(
            player=player,
            submission_status=PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
        )
        submission.status = PlayerRegistration.RegistrationStatus.INACTIVE
        submission.save(update_fields=["status"])
        submission.requested_competition_editions.add(self.edition)
        result = approve_player_registration_submission(
            submission_id=submission.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Registration approved.",
        )
        self.assertEqual(result["eligibility_created_count"], 1)
        self.assertTrue(result["eligibility_review_required"])
        eligibility = result["pending_eligibilities"][0]
        self.assertEqual(
            eligibility.status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )
        self.assertEqual(
            eligibility.registration,
            result["authoritative_registration"],
        )

    def test_renewal_approval_links_pending_to_successor(self):
        player = self._player("EU-RENEWAL")
        previous = self._registration(player=player)
        _, next_edition = self._edition("renewal-cup", self.next_season)
        submission = self._submission(
            player=player,
            season=self.next_season,
            submission_status=PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
            registration_type=PlayerRegistration.RegistrationType.SEASON_RENEWAL,
            registered_date=date(2027, 1, 1),
        )
        submission.status = PlayerRegistration.RegistrationStatus.INACTIVE
        submission.save(update_fields=["status"])
        submission.requested_competition_editions.add(next_edition)
        result = approve_player_registration_submission(
            submission_id=submission.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Renewal approved.",
        )
        successor = result["authoritative_registration"]
        previous.refresh_from_db()
        self.assertEqual(previous.status, UnionPlayerRegistration.Status.EXPIRED)
        self.assertEqual(successor.predecessor, previous)
        self.assertEqual(
            result["pending_eligibilities"][0].registration,
            successor,
        )

    def test_competition_registration_reuses_registration_for_pending(self):
        player = self._player("EU-COMPETITION")
        active = self._registration(player=player)
        submission = self._submission(
            player=player,
            submission_status=PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
            registration_type=(
                PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
            ),
        )
        submission.status = PlayerRegistration.RegistrationStatus.INACTIVE
        submission.save(update_fields=["status"])
        submission.requested_competition_editions.add(self.edition)
        result = approve_player_registration_submission(
            submission_id=submission.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Competition request accepted for eligibility review.",
        )
        self.assertEqual(result["authoritative_registration"], active)
        self.assertEqual(result["pending_eligibilities"][0].registration, active)
        self.assertEqual(
            UnionPlayerRegistration.objects.filter(player=player).count(),
            1,
        )

    def test_registration_approval_replay_returns_same_eligibility(self):
        player = self._player(
            "EU-REPLAY",
            player_status=UnionPlayer.Status.PROVISIONAL,
        )
        submission = self._submission(
            player=player,
            submission_status=PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
        )
        submission.status = PlayerRegistration.RegistrationStatus.INACTIVE
        submission.save(update_fields=["status"])
        submission.requested_competition_editions.add(self.edition)
        first = approve_player_registration_submission(
            submission_id=submission.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Registration approved.",
        )
        replay = approve_player_registration_submission(
            submission_id=submission.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Registration approved.",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["eligibility_created_count"], 0)
        self.assertEqual(replay["eligibility_existing_count"], 1)
        self.assertEqual(
            replay["pending_eligibilities"][0].id,
            first["pending_eligibilities"][0].id,
        )

    def test_validation_passes_active_contract_and_reports_warnings_and_capabilities(
        self,
    ):
        eligibility = self._eligibility()
        result = validate_player_competition_eligibility(
            eligibility=eligibility,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["blocking_errors"], [])
        warning_codes = {item["code"] for item in result["review_warnings"]}
        self.assertIn("PLAYER_IDENTITY_PROVISIONAL", warning_codes)
        self.assertIn("ELIGIBILITY_RULE_ENGINE_INCOMPLETE", warning_codes)
        capability_codes = {item["code"] for item in result["capability_notes"]}
        self.assertEqual(
            capability_codes,
            {
                "COMPETITION_SQUAD_LIMIT_CHECK_UNAVAILABLE",
                "CUP_TIED_RULE_CHECK_UNAVAILABLE",
                "DISCIPLINARY_DETAIL_CHECK_LIMITED",
                "PAYMENT_CHECK_UNAVAILABLE",
                "FOREIGN_PLAYER_RULE_ENGINE_UNAVAILABLE",
            },
        )

    def test_validation_blocks_registration_identity_and_season_mismatches(self):
        eligibility = self._eligibility()
        other_player = self._player("EU-OTHER")
        other_club = Club.objects.create(
            name="Eligibility Other Club",
            slug="eligibility-other-club",
        )
        cases = [
            ("status", UnionPlayerRegistration.Status.SUSPENDED),
            ("player", other_player),
            ("club", other_club),
            ("season", self.next_season),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                original = getattr(self.registration, field)
                setattr(self.registration, field, value)
                self.registration.save(update_fields=[field])
                eligibility.refresh_from_db()
                result = validate_player_competition_eligibility(
                    eligibility=eligibility,
                    reviewer=self.reviewer,
                    membership=self.membership,
                )
                self.assertTrue(result["blocking_errors"])
                setattr(self.registration, field, original)
                self.registration.save(update_fields=[field])

    def test_validation_blocks_non_approved_player_statuses(self):
        eligibility = self._eligibility()
        for player_status in (
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        ):
            with self.subTest(player_status=player_status):
                self.player.status = player_status
                self.player.save(update_fields=["status"])
                eligibility.refresh_from_db()
                result = validate_player_competition_eligibility(
                    eligibility=eligibility,
                    reviewer=self.reviewer,
                    membership=self.membership,
                )
                self.assertTrue(result["blocking_errors"])

    def test_validation_blocks_non_reviewable_edition_statuses(self):
        eligibility = self._eligibility()
        for edition_status in (
            CompetitionEdition.Status.DRAFT,
            CompetitionEdition.Status.CANCELLED,
            CompetitionEdition.Status.COMPLETED,
            CompetitionEdition.Status.ARCHIVED,
        ):
            with self.subTest(edition_status=edition_status):
                self.edition.status = edition_status
                self.edition.save(update_fields=["status"])
                eligibility.refresh_from_db()
                result = validate_player_competition_eligibility(
                    eligibility=eligibility,
                    reviewer=self.reviewer,
                    membership=self.membership,
                )
                self.assertTrue(result["blocking_errors"])

    def test_validation_blocks_invalid_dates_and_existing_eligible_record(self):
        eligibility = self._eligibility()
        eligibility.eligible_from = date(2026, 8, 1)
        eligibility.eligible_until = date(2026, 7, 1)
        result = validate_player_competition_eligibility(
            eligibility=eligibility,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        self.assertIn(
            "ELIGIBILITY_DATE_ORDER_INVALID",
            {item["code"] for item in result["blocking_errors"]},
        )

        eligibility.eligible_from = None
        eligibility.eligible_until = None
        other_submission = self._submission()
        UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            source_submission=other_submission,
            club=self.club,
            team=self.team,
            competition_identity=self.identity,
            competition_edition=self.edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        result = validate_player_competition_eligibility(
            eligibility=eligibility,
            reviewer=self.reviewer,
            membership=self.membership,
        )
        self.assertIn(
            "ELIGIBLE_RECORD_CONFLICT",
            {item["code"] for item in result["blocking_errors"]},
        )

    def test_approval_requires_reason_permission_workspace_and_scopes(self):
        eligibility = self._eligibility()
        with self.assertRaises(ValidationError):
            self._approve_eligibility(eligibility, reason=" ")

        manager = self._user("manager")
        manager_membership = self._membership(
            manager,
            UnionWorkspaceMembership.Role.COMPETITIONS_MANAGER,
        )
        with self.assertRaises(ValidationError):
            self._approve_eligibility(
                eligibility,
                reviewer=manager,
                membership=manager_membership,
            )

        other_union = Union.objects.create(
            name="Isolation Union",
            slug="isolation-union",
        )
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Isolation Workspace",
            slug="isolation-workspace",
            acronym="IW",
            sport="Football",
        )
        other_membership = self._membership(
            self.reviewer,
            UnionWorkspaceMembership.Role.REGISTRAR,
            workspace=other_workspace,
        )
        with self.assertRaises(ValidationError):
            self._approve_eligibility(
                eligibility,
                membership=other_membership,
            )

        for restrictions in (
            {"club_ids": []},
            {"competition_identity_ids": []},
            {"competition_edition_ids": []},
        ):
            with self.subTest(restrictions=restrictions):
                self.membership.scope_restrictions = restrictions
                self.membership.save(update_fields=["scope_restrictions"])
                with self.assertRaises(ValidationError):
                    self._approve_eligibility(eligibility)

    def test_pending_approval_records_decision_audit_notification_and_idempotency(self):
        eligibility = self._eligibility()
        with self.captureOnCommitCallbacks(execute=True):
            first = self._approve_eligibility(eligibility)
        approved = first["eligibility"]
        self.assertFalse(first["idempotent_replay"])
        self.assertEqual(
            approved.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        self.assertEqual(approved.reviewed_by, self.reviewer)
        self.assertIsNotNone(approved.reviewed_at)
        self.assertTrue(approved.decision_reason)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="competition_eligibility.approved"
            ).exists()
        )
        self.assertEqual(Notification.objects.filter(user=self.submitter).count(), 1)
        audit_count = UnionAuditEvent.objects.filter(
            action="competition_eligibility.approved"
        ).count()
        replay = self._approve_eligibility(approved)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["eligibility"].id, approved.id)
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action="competition_eligibility.approved"
            ).count(),
            audit_count,
        )

    def test_duplicate_eligible_record_blocks_approval(self):
        pending = self._eligibility()
        other_submission = self._submission()
        UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            source_submission=other_submission,
            club=self.club,
            team=self.team,
            competition_identity=self.identity,
            competition_edition=self.edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        with self.assertRaises(EligibilityValidationError):
            self._approve_eligibility(pending)
        pending.refresh_from_db()
        self.assertEqual(
            pending.status,
            UnionPlayerCompetitionEligibility.Status.PENDING,
        )

    def test_rejection_preserves_registration_player_and_history(self):
        eligibility = self._eligibility()
        rejected = reject_player_competition_eligibility(
            eligibility_id=eligibility.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Competition requirements were not met.",
        )
        self.assertEqual(
            rejected.status,
            UnionPlayerCompetitionEligibility.Status.REJECTED,
        )
        self.assertTrue(UnionPlayerRegistration.objects.filter(pk=self.registration.pk))
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="competition_eligibility.rejected"
            ).exists()
        )

    def test_suspension_and_reinstatement_preserve_history(self):
        eligibility = self._approve_eligibility(self._eligibility())["eligibility"]
        original_decision = eligibility.decision_reason
        with self.captureOnCommitCallbacks(execute=True):
            suspended = suspend_player_competition_eligibility(
                eligibility_id=eligibility.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Edition-specific disciplinary restriction.",
            )
        self.assertEqual(
            suspended.status,
            UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        )
        self.assertEqual(suspended.decision_reason, original_decision)
        self.assertTrue(suspended.restriction_reason)
        self.player.refresh_from_db()
        self.registration.refresh_from_db()
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)
        self.assertEqual(
            self.registration.status,
            UnionPlayerRegistration.Status.ACTIVE,
        )
        with self.captureOnCommitCallbacks(execute=True):
            reinstated = reinstate_player_competition_eligibility(
                eligibility_id=eligibility.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Restriction was cleared.",
            )
        self.assertEqual(
            reinstated.status,
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        self.assertEqual(reinstated.restriction_reason, "")
        actions = set(UnionAuditEvent.objects.values_list("action", flat=True))
        self.assertIn("competition_eligibility.suspended", actions)
        self.assertIn("competition_eligibility.reinstated", actions)
        self.assertEqual(Notification.objects.filter(user=self.submitter).count(), 2)

    def test_reinstatement_reruns_validation_and_blocks_invalid_state(self):
        eligibility = self._approve_eligibility(self._eligibility())["eligibility"]
        suspend_player_competition_eligibility(
            eligibility_id=eligibility.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Temporary restriction.",
        )
        self.registration.status = UnionPlayerRegistration.Status.SUSPENDED
        self.registration.save(update_fields=["status"])
        with self.assertRaises(EligibilityValidationError):
            reinstate_player_competition_eligibility(
                eligibility_id=eligibility.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Attempt invalid reinstatement.",
            )
        eligibility.refresh_from_db()
        self.assertEqual(
            eligibility.status,
            UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        )

    def test_eligible_and_suspended_eligibility_may_expire(self):
        eligible = self._approve_eligibility(self._eligibility())["eligibility"]
        expired = expire_player_competition_eligibility(
            eligibility_id=eligible.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Competition completed.",
        )
        self.assertEqual(
            expired.status,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        )

        second_submission = self._submission()
        second_submission.requested_competition_editions.add(self.edition)
        second = self._create_pending(
            submission=second_submission,
            registration=self.registration,
        )["eligibilities"][0]
        second_eligible = self._approve_eligibility(second)["eligibility"]
        suspended = suspend_player_competition_eligibility(
            eligibility_id=second_eligible.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Temporary restriction.",
        )
        expired_suspended = expire_player_competition_eligibility(
            eligibility_id=suspended.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Season closed.",
        )
        self.assertEqual(
            expired_suspended.status,
            UnionPlayerCompetitionEligibility.Status.EXPIRED,
        )

    def test_pending_may_cancel_and_terminal_rows_cannot_reopen_or_delete(self):
        eligibility = self._eligibility()
        cancelled = cancel_player_competition_eligibility(
            eligibility_id=eligibility.id,
            reviewer=self.reviewer,
            membership=self.membership,
            reason="Request was created in error.",
        )
        self.assertEqual(
            cancelled.status,
            UnionPlayerCompetitionEligibility.Status.CANCELLED,
        )
        with self.assertRaises(ValidationError):
            self._approve_eligibility(cancelled)
        with self.assertRaises(ValidationError):
            reinstate_player_competition_eligibility(
                eligibility_id=cancelled.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Illegal reopen.",
            )
        self.assertTrue(
            UnionPlayerCompetitionEligibility.objects.filter(pk=eligibility.pk).exists()
        )
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="competition_eligibility.cancelled"
            ).exists()
        )
