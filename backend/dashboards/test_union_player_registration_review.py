from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Club, Notification, User
from teams.models import PlayerRegistration, Team
from teams.player_submission_services import SubmissionValidationError

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
    UnionPlayerRegistration,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_player_review_services import (
    approve_player_registration_submission,
    assign_player_registration_reviewer,
    reject_player_registration_submission,
    request_player_registration_changes,
    start_player_registration_review,
)


class UnionPlayerRegistrationReviewTests(TestCase):
    list_url = "/api/dashboards/union-admin/player-registration-submissions/"
    registrations_url = "/api/dashboards/union-admin/player-registrations/"

    def setUp(self):
        self.client = APIClient()
        self.union = Union.objects.create(name="Review Union", slug="review-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Review Workspace",
            slug="review-workspace",
            acronym="RW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Review League",
            slug="review-league",
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
        self.submitter = self._user("submitter")
        self.reviewer = self._user("reviewer")
        self.membership = self._membership(
            self.reviewer,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.club = Club.objects.create(
            name="Review Club",
            slug="review-club",
            admin=self.submitter,
        )
        self.team = Team.objects.create(club=self.club, name="Review First Team")
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.season,
        )
        self.player = self._player("P000001")
        self.submission = self._submission()
        self._counter = 1

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
        extra_permissions=None,
        is_active=True,
    ):
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace or self.workspace,
            role=role,
            scope_restrictions=scope_restrictions or {},
            extra_permissions=extra_permissions or [],
            is_active=is_active,
        )

    def _player(self, number, *, union=None, player_status=None):
        return UnionPlayer.objects.create(
            union=union or self.union,
            union_player_number=f"RU-{number}",
            first_name="Amina",
            last_name=number,
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=player_status or UnionPlayer.Status.PROVISIONAL,
        )

    def _submission(
        self,
        *,
        club=None,
        team=None,
        player=None,
        workspace=None,
        season=None,
        submission_status=None,
        registration_type=None,
        registered_date=None,
        submitted_by=None,
    ):
        number = PlayerRegistration.objects.count() + 1
        effective_date = registered_date or date(2026, 2, 1)
        return PlayerRegistration.objects.create(
            club=club or self.club,
            team=team or self.team,
            registration_number=f"UNION-SUB-{number}",
            first_name="Amina",
            last_name=f"Player {number}",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            position="MID",
            registered_date=effective_date,
            expiry_date=effective_date + timedelta(days=300),
            union_workspace=workspace or self.workspace,
            union_player=player or self.player,
            season_record=season or self.season,
            supporting_documents=["document-reference"],
            club_notes="Club-maintained note",
            submitted_by=submitted_by or self.submitter,
            submitted_at=timezone.now(),
            submission_revision=1,
            submission_status=(
                submission_status or PlayerRegistration.SubmissionStatus.SUBMITTED
            ),
            registration_type=(
                registration_type
                or PlayerRegistration.RegistrationType.FIRST_REGISTRATION
            ),
            status=PlayerRegistration.RegistrationStatus.INACTIVE,
        )

    def _authoritative(
        self,
        *,
        player=None,
        club=None,
        team=None,
        season=None,
        effective_from=None,
        status_value=None,
    ):
        return UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player or self.player,
            club=club or self.club,
            team=team or self.team,
            season=season or self.season,
            status=status_value or UnionPlayerRegistration.Status.ACTIVE,
            registration_type=PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
            effective_from=effective_from or date(2026, 1, 1),
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )

    def _authenticate(self, user=None):
        self.client.force_authenticate(user or self.reviewer)

    def _start(self, submission=None):
        return start_player_registration_review(
            submission_id=(submission or self.submission).id,
            reviewer=self.reviewer,
            membership=self.membership,
        )

    def _approve(self, submission=None, *, reviewer=None, membership=None):
        return approve_player_registration_submission(
            submission_id=(submission or self.submission).id,
            reviewer=reviewer or self.reviewer,
            membership=membership or self.membership,
            reason="Identity and registration checks passed.",
        )

    def test_list_requires_workspace_access_and_registration_permission(self):
        self._authenticate()
        response = self.client.get(self.list_url, {"workspace": self.workspace.slug})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.submission.id)
        self.assertNotIn("supporting_documents", response.data["results"][0])

        missing = self.client.get(self.list_url)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        outsider = self._user("outsider")
        self._authenticate(outsider)
        denied = self.client.get(self.list_url, {"workspace": self.workspace.slug})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        viewer = self._user("no-registration-permission")
        self._membership(viewer, UnionWorkspaceMembership.Role.REFEREE_MANAGER)
        self._authenticate(viewer)
        permission_denied = self.client.get(
            self.list_url,
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(
            permission_denied.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_defaults_filters_search_and_ordering(self):
        draft = self._submission(
            player=self._player("P000002"),
            submission_status=PlayerRegistration.SubmissionStatus.DRAFT,
        )
        withdrawn = self._submission(
            player=self._player("P000003"),
            submission_status=PlayerRegistration.SubmissionStatus.WITHDRAWN,
        )
        self._authenticate()
        response = self.client.get(
            self.list_url,
            {
                "workspace": self.workspace.slug,
                "search": self.submission.registration_number,
                "ordering": "-submitted_at",
            },
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.submission.id)
        explicit_draft = self.client.get(
            self.list_url,
            {
                "workspace": self.workspace.slug,
                "submission_status": "DRAFT",
            },
        )
        self.assertEqual(explicit_draft.data["results"][0]["id"], draft.id)
        self.assertNotEqual(explicit_draft.data["results"][0]["id"], withdrawn.id)

    def test_club_and_competition_scopes_filter_list_and_detail(self):
        restricted_user = self._user("restricted")
        restricted = self._membership(
            restricted_user,
            UnionWorkspaceMembership.Role.REGISTRAR,
            scope_restrictions={"club_ids": []},
        )
        self._authenticate(restricted_user)
        response = self.client.get(self.list_url, {"workspace": self.workspace.slug})
        self.assertEqual(response.data, {"count": 0, "results": []})
        detail = self.client.get(
            f"{self.list_url}{self.submission.id}/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Scoped Cup",
            slug="scoped-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Scoped Cup 2026",
            slug="scoped-cup-2026",
            season="2026",
            season_record=self.season,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
        )
        self.submission.requested_competition_editions.add(edition)
        restricted.scope_restrictions = {
            "club_ids": [self.club.id],
            "competition_identity_ids": [identity.id],
            "competition_edition_ids": [],
        }
        restricted.save(update_fields=["scope_restrictions"])
        response = self.client.get(self.list_url, {"workspace": self.workspace.slug})
        self.assertEqual(response.data["count"], 0)

    def test_cross_workspace_and_legacy_detail_return_not_found(self):
        other_union = Union.objects.create(name="Other Union", slug="other-union")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other Workspace",
            slug="other-workspace",
            acronym="OW",
            sport="Football",
        )
        cross_workspace = self._submission(
            player=self._player("P000004", union=other_union),
            workspace=other_workspace,
        )
        legacy = self._submission(
            player=self._player("P000005"),
            submission_status=PlayerRegistration.SubmissionStatus.LEGACY,
        )
        self._authenticate()
        for submission in (cross_workspace, legacy):
            with self.subTest(submission=submission.id):
                response = self.client.get(
                    f"{self.list_url}{submission.id}/",
                    {"workspace": self.workspace.slug},
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reviewer_assignment_contract(self):
        assigned = self._user("assigned")
        self._membership(assigned, UnionWorkspaceMembership.Role.REGISTRAR)
        updated = assign_player_registration_reviewer(
            submission_id=self.submission.id,
            reviewer=self.reviewer,
            assigned_user=assigned,
            membership=self.membership,
        )
        self.assertEqual(updated.assigned_reviewer, assigned)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="player_registration.reviewer_assigned"
            ).exists()
        )

        no_membership = self._user("unassigned")
        with self.assertRaises(ValidationError):
            assign_player_registration_reviewer(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                assigned_user=no_membership,
                membership=self.membership,
            )
        no_review_permission = self._user("official")
        self._membership(
            no_review_permission,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        with self.assertRaises(ValidationError):
            assign_player_registration_reviewer(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                assigned_user=no_review_permission,
                membership=self.membership,
            )

    def test_start_review_transition_and_fresh_validation(self):
        self.submission.automatic_validation = {"stale": True}
        self.submission.save(update_fields=["automatic_validation"])
        updated = self._start()
        self.assertEqual(
            updated.submission_status,
            PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
        )
        self.assertEqual(updated.assigned_reviewer, self.reviewer)
        self.assertNotIn("stale", updated.automatic_validation)
        self.assertIn("blocking_errors", updated.automatic_validation)
        actions = set(UnionAuditEvent.objects.values_list("action", flat=True))
        self.assertIn("player_registration.review_started", actions)
        self.assertIn("player_registration.validation_completed", actions)

    def test_review_start_rejects_illegal_state_but_keeps_blockers_visible(self):
        self.submission.submission_status = PlayerRegistration.SubmissionStatus.DRAFT
        self.submission.save(update_fields=["submission_status"])
        with self.assertRaises(ValidationError):
            self._start()
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.SUBMITTED
        )
        self.submission.supporting_documents = []
        self.submission.save(
            update_fields=["submission_status", "supporting_documents"]
        )
        updated = self._start()
        self.assertTrue(updated.automatic_validation["blocking_errors"])

    def test_request_changes_requires_reason_and_under_review_state(self):
        with self.assertRaises(ValidationError):
            request_player_registration_changes(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason=" ",
            )
        with self.assertRaises(ValidationError):
            request_player_registration_changes(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Correct documents.",
            )

    def test_request_changes_preserves_club_data_and_writes_audit(self):
        self._start()
        with self.captureOnCommitCallbacks(execute=True):
            updated = request_player_registration_changes(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Upload a clearer document.",
            )
        self.assertEqual(
            updated.submission_status,
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED,
        )
        self.assertEqual(updated.change_request_reason, "Upload a clearer document.")
        self.assertEqual(updated.club_notes, "Club-maintained note")
        self.assertEqual(updated.supporting_documents, ["document-reference"])
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="player_registration.changes_requested"
            ).exists()
        )
        self.assertEqual(
            Notification.objects.filter(user=self.submitter).count(),
            1,
        )

    def test_rejection_requires_approval_permission_reason_and_review_state(self):
        manager = self._user("manager")
        manager_membership = self._membership(
            manager,
            UnionWorkspaceMembership.Role.COMPETITIONS_MANAGER,
        )
        self._start()
        with self.assertRaises(ValidationError):
            reject_player_registration_submission(
                submission_id=self.submission.id,
                reviewer=manager,
                membership=manager_membership,
                reason="Not eligible.",
            )
        with self.assertRaises(ValidationError):
            reject_player_registration_submission(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason=" ",
            )

    def test_submitter_cannot_make_final_decision(self):
        submitter_membership = self._membership(
            self.submitter,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self._start()
        for service in (
            approve_player_registration_submission,
            reject_player_registration_submission,
        ):
            with self.subTest(service=service.__name__):
                with self.assertRaises(SubmissionValidationError):
                    service(
                        submission_id=self.submission.id,
                        reviewer=self.submitter,
                        membership=submitter_membership,
                        reason="Self decision.",
                    )

    def test_rejection_preserves_history_creates_no_registration_and_notifies(self):
        self._start()
        original_submitted_at = self.submission.submitted_at
        with self.captureOnCommitCallbacks(execute=True):
            rejected = reject_player_registration_submission(
                submission_id=self.submission.id,
                reviewer=self.reviewer,
                membership=self.membership,
                reason="Eligibility evidence was insufficient.",
            )
        self.assertEqual(
            rejected.submission_status,
            PlayerRegistration.SubmissionStatus.REJECTED,
        )
        self.assertEqual(
            rejected.status,
            PlayerRegistration.RegistrationStatus.INACTIVE,
        )
        self.assertEqual(rejected.submitted_at, original_submitted_at)
        self.assertEqual(UnionPlayerRegistration.objects.count(), 0)
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, UnionPlayer.Status.PROVISIONAL)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="player_registration.rejected"
            ).exists()
        )
        self.assertEqual(Notification.objects.filter(user=self.submitter).count(), 1)

    def test_first_approval_creates_authoritative_registration_and_promotes_player(
        self,
    ):
        self._start()
        with self.captureOnCommitCallbacks(execute=True):
            result = self._approve()
        registration = result["authoritative_registration"]
        self.assertEqual(UnionPlayerRegistration.objects.count(), 1)
        self.assertEqual(registration.source_registration, self.submission)
        self.assertEqual(registration.season, self.season)
        self.assertEqual(
            registration.registration_type,
            PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
        )
        self.assertEqual(registration.status, UnionPlayerRegistration.Status.ACTIVE)
        self.player.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.player.status, UnionPlayer.Status.APPROVED)
        self.assertEqual(self.player.identity_verified_by, self.reviewer)
        self.assertIsNotNone(self.player.identity_verified_at)
        self.assertEqual(
            self.submission.submission_status,
            PlayerRegistration.SubmissionStatus.APPROVED,
        )
        self.assertEqual(
            self.submission.status,
            PlayerRegistration.RegistrationStatus.ACTIVE,
        )
        actions = set(UnionAuditEvent.objects.values_list("action", flat=True))
        self.assertIn("player_registration.approved", actions)
        self.assertIn("union_player_registration.created", actions)
        self.assertEqual(Notification.objects.filter(user=self.submitter).count(), 1)

    def test_first_approval_is_idempotent(self):
        self._start()
        first = self._approve()
        irreversible_count = UnionAuditEvent.objects.filter(
            action__in=[
                "player_registration.approved",
                "union_player_registration.created",
            ]
        ).count()
        replay = self._approve()
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            replay["authoritative_registration"].id,
            first["authoritative_registration"].id,
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), 1)
        self.assertEqual(
            UnionAuditEvent.objects.filter(
                action__in=[
                    "player_registration.approved",
                    "union_player_registration.created",
                ]
            ).count(),
            irreversible_count,
        )

    def test_existing_active_registration_blocks_duplicate_first_approval(self):
        self._authoritative()
        self._start()
        with self.assertRaises(SubmissionValidationError) as context:
            self._approve()
        codes = {
            item["code"]
            for item in context.exception.automatic_validation["blocking_errors"]
        }
        self.assertIn("ACTIVE_REGISTRATION_CONFLICT", codes)
        self.assertEqual(UnionPlayerRegistration.objects.count(), 1)

    def test_invalid_player_statuses_block_approval(self):
        for player_status in (
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        ):
            with self.subTest(player_status=player_status):
                player = self._player(
                    f"INVALID-{player_status}",
                    player_status=player_status,
                )
                submission = self._submission(player=player)
                self._start(submission)
                with self.assertRaises(SubmissionValidationError):
                    self._approve(submission)

    def test_fresh_blocking_validation_and_dual_registration_prevent_approval(self):
        self._start()
        self.submission.supporting_documents = []
        self.submission.save(update_fields=["supporting_documents"])
        with self.assertRaises(SubmissionValidationError):
            self._approve()

        dual = self._submission(
            player=self._player("DUAL"),
            registration_type=PlayerRegistration.RegistrationType.DUAL_REGISTRATION,
        )
        self._start(dual)
        with self.assertRaises(SubmissionValidationError) as context:
            self._approve(dual)
        messages = [
            item["message"]
            for item in context.exception.automatic_validation["blocking_errors"]
        ]
        self.assertIn(
            "Full dual-registration rules are not yet implemented.",
            messages,
        )

    def test_season_renewal_expires_previous_and_creates_linked_successor(self):
        previous = self._authoritative()
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.WITHDRAWN
        )
        self.submission.save(update_fields=["submission_status"])
        renewal = self._submission(
            season=self.next_season,
            registration_type=PlayerRegistration.RegistrationType.SEASON_RENEWAL,
            registered_date=date(2027, 1, 1),
        )
        self._start(renewal)
        result = self._approve(renewal)
        successor = result["authoritative_registration"]
        previous.refresh_from_db()
        self.assertEqual(previous.status, UnionPlayerRegistration.Status.EXPIRED)
        self.assertEqual(previous.effective_to, date(2026, 12, 31))
        self.assertTrue(UnionPlayerRegistration.objects.filter(pk=previous.pk).exists())
        self.assertEqual(successor.predecessor, previous)
        self.assertEqual(successor.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(UnionPlayerRegistration.objects.count(), 2)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="union_player_registration.renewed"
            ).exists()
        )

    def test_cross_club_and_invalid_date_renewals_are_blocked(self):
        other_club = Club.objects.create(name="Other Club", slug="other-club")
        other_team = Team.objects.create(club=other_club, name="Other Team")
        LeagueClubMembership.objects.create(
            league=self.league,
            club=other_club,
            season=self.next_season,
        )
        self._authoritative(club=other_club, team=other_team)
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.WITHDRAWN
        )
        self.submission.save(update_fields=["submission_status"])
        cross_club = self._submission(
            season=self.next_season,
            registration_type=PlayerRegistration.RegistrationType.SEASON_RENEWAL,
            registered_date=date(2027, 1, 1),
        )
        self._start(cross_club)
        with self.assertRaises(SubmissionValidationError):
            self._approve(cross_club)

        cross_club.submission_status = PlayerRegistration.SubmissionStatus.WITHDRAWN
        cross_club.save(update_fields=["submission_status"])
        UnionPlayerRegistration.objects.all().delete()
        self._authoritative(effective_from=date(2026, 6, 1))
        invalid_date = self._submission(
            season=self.next_season,
            registration_type=PlayerRegistration.RegistrationType.SEASON_RENEWAL,
            registered_date=date(2026, 5, 1),
        )
        self._start(invalid_date)
        with self.assertRaises(SubmissionValidationError):
            self._approve(invalid_date)

    def test_competition_registration_reuses_active_registration(self):
        active = self._authoritative()
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.WITHDRAWN
        )
        self.submission.save(update_fields=["submission_status"])
        competition_submission = self._submission(
            registration_type=(
                PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
            ),
        )
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Registration Review Cup",
            slug="registration-review-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Registration Review Cup 2026",
            slug="registration-review-cup-2026",
            season="2026",
            season_record=self.season,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.REGISTRATION_OPEN,
        )
        competition_submission.requested_competition_editions.add(edition)
        self._start(competition_submission)
        result = self._approve(competition_submission)
        self.assertEqual(result["authoritative_registration"], active)
        self.assertTrue(result["eligibility_review_required"])
        self.assertEqual(UnionPlayerRegistration.objects.count(), 1)

    def test_competition_registration_requires_active_same_club_registration(self):
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.WITHDRAWN
        )
        self.submission.save(update_fields=["submission_status"])
        competition_submission = self._submission(
            registration_type=(
                PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
            ),
        )
        self._start(competition_submission)
        with self.assertRaises(SubmissionValidationError):
            self._approve(competition_submission)

    def test_action_endpoints_require_post_workspace_and_written_reason(self):
        self._authenticate()
        missing_workspace = self.client.post(
            f"{self.list_url}{self.submission.id}/start-review/",
            {},
            format="json",
        )
        self.assertEqual(
            missing_workspace.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        started = self.client.post(
            f"{self.list_url}{self.submission.id}/start-review/",
            {"workspace": self.workspace.slug},
            format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_200_OK)
        blank_reason = self.client.post(
            f"{self.list_url}{self.submission.id}/approve/",
            {"workspace": self.workspace.slug, "reason": " "},
            format="json",
        )
        self.assertEqual(blank_reason.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authoritative_read_apis_are_workspace_scoped_and_read_only(self):
        registration = self._authoritative()
        self._authenticate()
        listing = self.client.get(
            self.registrations_url,
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        detail_url = f"{self.registrations_url}{registration.id}/"
        detail = self.client.get(
            detail_url,
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["id"], registration.id)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    detail_url,
                    {"workspace": self.workspace.slug},
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )

    def test_authoritative_reads_enforce_club_and_workspace_scope(self):
        registration = self._authoritative()
        restricted_user = self._user("read-restricted")
        self._membership(
            restricted_user,
            UnionWorkspaceMembership.Role.VIEWER,
            scope_restrictions={"club_ids": []},
        )
        self._authenticate(restricted_user)
        listing = self.client.get(
            self.registrations_url,
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(listing.data, {"count": 0, "results": []})
        detail = self.client.get(
            f"{self.registrations_url}{registration.id}/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        other_union = Union.objects.create(name="Read Other Union", slug="read-other")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Read Other Workspace",
            slug="read-other-workspace",
            acronym="ROW",
            sport="Football",
        )
        other_player = self._player("READ-OTHER", union=other_union)
        other_registration = UnionPlayerRegistration.objects.create(
            workspace=other_workspace,
            player=other_player,
            club=self.club,
            team=self.team,
            status=UnionPlayerRegistration.Status.ACTIVE,
            registration_type=PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
            effective_from=date(2026, 1, 1),
        )
        self.membership.scope_restrictions = {}
        self.membership.save(update_fields=["scope_restrictions"])
        self._authenticate()
        cross_detail = self.client.get(
            f"{self.registrations_url}{other_registration.id}/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(cross_detail.status_code, status.HTTP_404_NOT_FOUND)
