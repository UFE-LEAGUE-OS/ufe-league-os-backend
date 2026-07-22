from datetime import date

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Club, User
from teams.models import PlayerRegistration, Team

from .models import (
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    League,
    LeagueClubMembership,
    Season,
    Union,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


class UnionPlayerEligibilityAPITests(TestCase):
    list_url = "/api/dashboards/union-admin/player-eligibilities/"

    def setUp(self):
        self.client = APIClient()
        self.union = Union.objects.create(name="API Eligibility Union", slug="api-eu")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="API Eligibility Workspace",
            slug="api-eligibility-workspace",
            acronym="AEW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="API Eligibility League",
            slug="api-eligibility-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026",
            slug="api-2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.reviewer = self._user("reviewer")
        self.submitter = self._user("submitter")
        self.membership = self._membership(
            self.reviewer,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.club = Club.objects.create(
            name="API Eligibility Club",
            slug="api-eligibility-club",
            admin=self.submitter,
        )
        self.team = Team.objects.create(club=self.club, name="API First Team")
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.season,
        )
        self.player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number="API-P000001",
            first_name="Sarah",
            last_name="Namuli",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            identity_reference="PRIVATE-IDENTITY-EVIDENCE",
            status=UnionPlayer.Status.APPROVED,
        )
        self.submission = self._submission()
        self.registration = self._registration()
        self.identity, self.edition = self._edition()
        self.eligibility = self._eligibility()

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
    ):
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace or self.workspace,
            role=role,
            scope_restrictions=scope_restrictions or {},
        )

    def _submission(self, *, player=None, workspace=None):
        number = PlayerRegistration.objects.count() + 1
        return PlayerRegistration.objects.create(
            club=self.club,
            team=self.team,
            registration_number=f"API-ELIG-SUB-{number}",
            first_name="Sarah",
            last_name="Namuli",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            position="MID",
            registered_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
            union_workspace=workspace or self.workspace,
            union_player=player or self.player,
            season_record=self.season,
            supporting_documents=["private-document-reference"],
            club_notes="Private Club note",
            submitted_by=self.submitter,
            submitted_at=timezone.now(),
            submission_revision=2,
            submission_status=PlayerRegistration.SubmissionStatus.APPROVED,
            registration_type=PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
            status=PlayerRegistration.RegistrationStatus.ACTIVE,
        )

    def _registration(self, *, player=None, workspace=None, submission=None):
        return UnionPlayerRegistration.objects.create(
            workspace=workspace or self.workspace,
            player=player or self.player,
            club=self.club,
            team=self.team,
            season=self.season,
            source_registration=submission or self.submission,
            status=UnionPlayerRegistration.Status.ACTIVE,
            registration_type=PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )

    def _edition(self, suffix="main"):
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name=f"API Eligibility Cup {suffix}",
            slug=f"api-eligibility-cup-{suffix}",
            default_eligibility_rules={"minimum_age": 16},
        )
        competition = Competition.objects.create(
            league=self.league,
            name=f"API Eligibility Cup {suffix} 2026",
            slug=f"api-eligibility-cup-{suffix}-2026",
            season="2026",
            season_record=self.season,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 11, 30),
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
            status=CompetitionEdition.Status.REGISTRATION_OPEN,
        )
        return identity, edition

    def _eligibility(
        self,
        *,
        eligibility_status=None,
        player=None,
        registration=None,
        submission=None,
        identity=None,
        edition=None,
        workspace=None,
    ):
        return UnionPlayerCompetitionEligibility.objects.create(
            workspace=workspace or self.workspace,
            player=player or self.player,
            registration=registration or self.registration,
            source_submission=submission or self.submission,
            club=self.club,
            team=self.team,
            competition_identity=identity or self.identity,
            competition_edition=edition or self.edition,
            season=self.season,
            status=eligibility_status
            or UnionPlayerCompetitionEligibility.Status.PENDING,
            warnings=[
                {
                    "code": "SOURCE_WARNING",
                    "field": "player",
                    "message": "Review source warning.",
                    "severity": "WARNING",
                }
            ],
        )

    def _authenticate(self, user=None):
        self.client.force_authenticate(user or self.reviewer)

    def _detail_url(self, eligibility=None):
        return f"{self.list_url}{(eligibility or self.eligibility).id}/"

    def _action_url(self, action, eligibility=None):
        return f"{self._detail_url(eligibility)}{action}/"

    def _post(self, action, eligibility=None, **data):
        payload = {
            "workspace": self.workspace.id,
            "reason": "Maintained eligibility decision.",
        }
        payload.update(data)
        return self.client.post(
            self._action_url(action, eligibility),
            payload,
            format="json",
        )

    def test_list_requires_workspace_and_view_permission(self):
        self._authenticate()
        response = self.client.get(self.list_url, {"workspace": self.workspace.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        missing = self.client.get(self.list_url)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        no_view = self._user("no-view")
        self._membership(no_view, UnionWorkspaceMembership.Role.MATCH_OFFICIAL)
        self._authenticate(no_view)
        denied = self.client.get(self.list_url, {"workspace": self.workspace.id})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_is_workspace_scoped_and_keeps_terminal_history(self):
        rejected = self._eligibility(
            eligibility_status=UnionPlayerCompetitionEligibility.Status.REJECTED,
            submission=self._submission(),
        )
        other_union = Union.objects.create(name="Other API Union", slug="other-api-eu")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other API Workspace",
            slug="other-api-workspace",
            acronym="OAW",
            sport="Football",
        )
        other_player = UnionPlayer.objects.create(
            union=other_union,
            union_player_number="OTHER-P1",
            first_name="Other",
            last_name="Player",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        other_submission = self._submission(
            player=other_player,
            workspace=other_workspace,
        )
        other_registration = self._registration(
            player=other_player,
            workspace=other_workspace,
            submission=other_submission,
        )
        self._eligibility(
            player=other_player,
            registration=other_registration,
            submission=other_submission,
            workspace=other_workspace,
        )
        self._authenticate()
        response = self.client.get(self.list_url, {"workspace": self.workspace.id})
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.eligibility.id, rejected.id})

    def test_list_applies_club_identity_and_edition_scopes(self):
        self._authenticate()
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
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id},
                )
                self.assertEqual(response.data, {"count": 0, "results": []})

    def test_list_filters_status_club_player_edition_and_season(self):
        rejected = self._eligibility(
            eligibility_status=UnionPlayerCompetitionEligibility.Status.REJECTED,
            submission=self._submission(),
        )
        self._authenticate()
        cases = [
            ({"status": "REJECTED"}, rejected.id),
            ({"club": self.club.id}, self.eligibility.id),
            ({"player": self.player.id}, self.eligibility.id),
            ({"competition_edition": self.edition.id}, self.eligibility.id),
            ({"season": self.season.id}, self.eligibility.id),
        ]
        for filters, expected_id in cases:
            with self.subTest(filters=filters):
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id, **filters},
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn(
                    expected_id,
                    {item["id"] for item in response.data["results"]},
                )
        multiple = self.client.get(
            f"{self.list_url}?workspace={self.workspace.id}"
            "&status=PENDING&status=REJECTED"
        )
        self.assertEqual(multiple.data["count"], 2)

    def test_list_searches_player_number_name_club_and_competition(self):
        self._authenticate()
        for search in (
            self.player.union_player_number,
            self.player.first_name,
            self.club.name,
            self.identity.name,
            self.edition.competition.name,
        ):
            with self.subTest(search=search):
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id, "search": search},
                )
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["id"],
                    self.eligibility.id,
                )

    def test_list_uses_safe_ordering_and_falls_back_to_default(self):
        second = self._eligibility(
            eligibility_status=UnionPlayerCompetitionEligibility.Status.REJECTED,
            submission=self._submission(),
        )
        self._authenticate()
        ordered = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id, "ordering": "player_name"},
        )
        self.assertEqual(ordered.status_code, status.HTTP_200_OK)
        fallback = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id, "ordering": "status;DROP TABLE"},
        )
        self.assertEqual(fallback.data["results"][0]["id"], second.id)

    def test_detail_is_scoped_and_excludes_private_fields(self):
        self._authenticate()
        response = self.client.get(
            self._detail_url(),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.eligibility.id)
        for private_field in (
            "identity_reference",
            "supporting_documents",
            "club_notes",
            "audit_metadata",
        ):
            self.assertNotIn(private_field, response.data)

        self.membership.scope_restrictions = {"club_ids": []}
        self.membership.save(update_fields=["scope_restrictions"])
        out_of_scope = self.client.get(
            self._detail_url(),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(out_of_scope.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_and_action_enforce_identity_and_edition_scopes(self):
        self._authenticate()
        for restrictions in (
            {"competition_identity_ids": []},
            {"competition_edition_ids": []},
        ):
            with self.subTest(restrictions=restrictions):
                self.membership.scope_restrictions = restrictions
                self.membership.save(update_fields=["scope_restrictions"])
                detail = self.client.get(
                    self._detail_url(),
                    {"workspace": self.workspace.id},
                )
                self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
                action = self._post("approve")
                self.assertEqual(action.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_workspace_detail_returns_not_found(self):
        other_union = Union.objects.create(
            name="Detail Other Union", slug="detail-other"
        )
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Detail Other Workspace",
            slug="detail-other-workspace",
            acronym="DOW",
            sport="Football",
        )
        other_player = UnionPlayer.objects.create(
            union=other_union,
            union_player_number="DETAIL-OTHER",
            first_name="Other",
            last_name="Detail",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        other_submission = self._submission(
            player=other_player,
            workspace=other_workspace,
        )
        other_registration = self._registration(
            player=other_player,
            workspace=other_workspace,
            submission=other_submission,
        )
        other = self._eligibility(
            player=other_player,
            registration=other_registration,
            submission=other_submission,
            workspace=other_workspace,
        )
        self._authenticate()
        response = self.client.get(
            self._detail_url(other),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_create_patch_put_and_delete_are_unavailable(self):
        self._authenticate()
        create = self.client.post(
            self.list_url,
            {"workspace": self.workspace.id},
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        for method in ("patch", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._detail_url(),
                    {"workspace": self.workspace.id},
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )

    def test_approval_requires_permission_reason_and_valid_date_order(self):
        viewer = self._user("viewer")
        self._membership(viewer, UnionWorkspaceMembership.Role.VIEWER)
        self._authenticate(viewer)
        denied = self.client.post(
            self._action_url("approve"),
            {"workspace": self.workspace.id, "reason": "Not authorised."},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self._authenticate()
        blank = self._post("approve", reason=" ")
        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)
        invalid_dates = self._post(
            "approve",
            eligible_from="2026-08-01",
            eligible_until="2026-07-01",
        )
        self.assertEqual(invalid_dates.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approval_returns_validation_dates_and_idempotency(self):
        self._authenticate()
        first = self._post(
            "approve",
            eligible_from="2026-08-01",
            eligible_until="2026-10-31",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["eligibility"]["status"], "ELIGIBLE")
        self.assertEqual(first.data["eligibility"]["eligible_from"], "2026-08-01")
        self.assertIsNotNone(first.data["automatic_validation"])
        self.assertFalse(first.data["idempotent_replay"])
        replay = self._post("approve")
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data["idempotent_replay"])
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.filter(
                source_submission=self.submission,
                competition_edition=self.edition,
            ).count(),
            1,
        )

    def test_approval_preserves_structured_validation_error(self):
        self.registration.status = UnionPlayerRegistration.Status.SUSPENDED
        self.registration.save(update_fields=["status"])
        self._authenticate()
        response = self._post("approve")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("automatic_validation", response.data)
        self.assertTrue(response.data["automatic_validation"]["blocking_errors"])

    def test_rejection_requires_reason_and_preserves_registration(self):
        self._authenticate()
        missing = self._post("reject", reason=" ")
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        response = self._post("reject")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["eligibility"]["status"], "REJECTED")
        self.assertIsNone(response.data["automatic_validation"])
        self.registration.refresh_from_db()
        self.assertEqual(
            self.registration.status, UnionPlayerRegistration.Status.ACTIVE
        )

    def test_suspend_contract_and_registration_boundary(self):
        self._authenticate()
        pending = self._post("suspend")
        self.assertEqual(pending.status_code, status.HTTP_400_BAD_REQUEST)
        self._post("approve")
        suspended = self._post("suspend")
        self.assertEqual(suspended.status_code, status.HTTP_200_OK)
        self.assertEqual(suspended.data["eligibility"]["status"], "SUSPENDED")
        self.assertTrue(suspended.data["eligibility"]["restriction_reason"])
        self.registration.refresh_from_db()
        self.assertEqual(
            self.registration.status, UnionPlayerRegistration.Status.ACTIVE
        )

    def test_reinstate_contract_and_structured_blocking_error(self):
        self._authenticate()
        not_suspended = self._post("reinstate")
        self.assertEqual(not_suspended.status_code, status.HTTP_400_BAD_REQUEST)
        self._post("approve")
        self._post("suspend")
        reinstated = self._post("reinstate")
        self.assertEqual(reinstated.status_code, status.HTTP_200_OK)
        self.assertEqual(reinstated.data["eligibility"]["status"], "ELIGIBLE")
        self.assertIsNone(reinstated.data["automatic_validation"])

        self._post("suspend")
        self.registration.status = UnionPlayerRegistration.Status.SUSPENDED
        self.registration.save(update_fields=["status"])
        blocked = self._post("reinstate")
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("automatic_validation", blocked.data)

    def test_expire_allows_eligible_and_suspended_but_not_pending(self):
        self._authenticate()
        pending = self._post("expire")
        self.assertEqual(pending.status_code, status.HTTP_400_BAD_REQUEST)
        self._post("approve")
        eligible = self._post("expire")
        self.assertEqual(eligible.data["eligibility"]["status"], "EXPIRED")

        second = self._eligibility(
            submission=self._submission(),
        )
        self._post("approve", second)
        self._post("suspend", second)
        suspended = self._post("expire", second)
        self.assertEqual(suspended.data["eligibility"]["status"], "EXPIRED")

    def test_cancel_allows_pending_but_not_eligible(self):
        self._authenticate()
        cancelled = self._post("cancel")
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        self.assertEqual(cancelled.data["eligibility"]["status"], "CANCELLED")

        second = self._eligibility(submission=self._submission())
        self._post("approve", second)
        denied = self._post("cancel", second)
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
