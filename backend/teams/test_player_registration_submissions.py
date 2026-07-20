from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, ClubAdminScope, User
from dashboards.models import (
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
)
from teams.models import PlayerRegistration, Team
from teams.player_submission_services import (
    _club_workspace,
    resubmit_player_registration,
    search_union_players_for_club,
    submit_player_registration,
    update_player_registration_draft,
    validate_player_registration_submission,
    withdraw_player_registration,
)


class PlayerRegistrationSubmissionServiceTests(TestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Submission Union", slug="submission-union"
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Submission Workspace",
            slug="submission-workspace",
            acronym="SW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union, name="Submission League", slug="submission-league"
        )
        self.season = Season.objects.create(
            league=self.league, name="2026", slug="2026"
        )
        self.actor = User.objects.create_user(
            email="club@leagueos.test",
            password="StrongPass123!",
            role=User.Role.CLUB_ADMIN,
        )
        self.club = Club.objects.create(
            name="Submission Club", slug="submission-club", admin=self.actor
        )
        LeagueClubMembership.objects.create(
            league=self.league, club=self.club, season=self.season
        )
        self.team = Team.objects.create(club=self.club, name="First Team")
        self.player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number="SU-P000001",
            first_name="Amina",
            last_name="Kato",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        self.submission = PlayerRegistration.objects.create(
            club=self.club,
            team=self.team,
            registration_number="SUB-1",
            first_name="Amina",
            last_name="Kato",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            position="MID",
            registered_date=date(2026, 1, 1),
            union_workspace=self.workspace,
            union_player=self.player,
            season_record=self.season,
            supporting_documents=["document-1"],
            submission_status=PlayerRegistration.SubmissionStatus.DRAFT,
        )

    def test_draft_update_and_submit_transition(self):
        updated = update_player_registration_draft(
            submission_id=self.submission.id,
            actor=self.actor,
            updates={"position": "FW"},
        )
        self.assertEqual(updated.position, "FW")
        submitted = submit_player_registration(
            submission_id=self.submission.id, actor=self.actor
        )
        self.assertEqual(
            submitted.submission_status, PlayerRegistration.SubmissionStatus.SUBMITTED
        )
        self.assertEqual(submitted.submission_revision, 1)
        self.assertIsNotNone(submitted.submitted_at)
        with self.assertRaises(ValidationError):
            update_player_registration_draft(
                submission_id=self.submission.id,
                actor=self.actor,
                updates={"position": "MID"},
            )

    def test_resubmit_preserves_original_submission_timestamp(self):
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        )
        self.submission.submitted_at = timezone.now()
        self.submission.save()
        original = self.submission.submitted_at
        resubmitted = resubmit_player_registration(
            submission_id=self.submission.id, actor=self.actor
        )
        self.assertEqual(
            resubmitted.submission_status, PlayerRegistration.SubmissionStatus.SUBMITTED
        )
        self.assertEqual(resubmitted.submitted_at, original)
        self.assertIsNotNone(resubmitted.last_resubmitted_at)
        self.assertEqual(resubmitted.submission_revision, 1)

    def test_withdrawal_is_legal_only_from_club_controlled_states(self):
        withdrawn = withdraw_player_registration(
            submission_id=self.submission.id,
            actor=self.actor,
            withdrawal_reason="Player withdrew",
        )
        self.assertEqual(
            withdrawn.submission_status, PlayerRegistration.SubmissionStatus.WITHDRAWN
        )
        self.assertTrue(
            PlayerRegistration.objects.filter(pk=self.submission.id).exists()
        )
        with self.assertRaises(ValidationError):
            withdraw_player_registration(
                submission_id=self.submission.id,
                actor=self.actor,
                withdrawal_reason="Again",
            )


class ClubWorkspaceResolutionTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            email="workspace-club-admin@leagueos.test",
            password="StrongPass123!",
            role=User.Role.CLUB_ADMIN,
        )
        self.club = Club.objects.create(
            name="Workspace Resolution Club",
            slug="workspace-resolution-club",
            admin=self.actor,
        )

    def _attach_workspace(self, suffix):
        union = Union.objects.create(
            name=f"Workspace Union {suffix}",
            slug=f"workspace-union-{suffix}",
        )
        workspace = UnionWorkspace.objects.create(
            related_union=union,
            name=f"Workspace {suffix}",
            slug=f"workspace-{suffix}",
            acronym=f"W{suffix}",
            sport="Football",
        )
        league = League.objects.create(
            union=union,
            name=f"Workspace League {suffix}",
            slug=f"workspace-league-{suffix}",
        )
        season = Season.objects.create(
            league=league,
            name=f"Season {suffix}",
            slug=f"season-{suffix}",
        )
        LeagueClubMembership.objects.create(
            league=league,
            club=self.club,
            season=season,
        )
        return workspace

    def test_no_active_workspace_is_rejected(self):
        with self.assertRaises(ValidationError) as context:
            _club_workspace(self.club)
        self.assertEqual(
            context.exception.message_dict,
            {
                "union_workspace_id": [
                    "This Club is not attached to an active Union workspace."
                ]
            },
        )

    def test_one_active_workspace_resolves_automatically(self):
        workspace = self._attach_workspace("one")
        self.assertEqual(_club_workspace(self.club), workspace)

    def test_ambiguous_workspace_requires_valid_explicit_selection(self):
        first = self._attach_workspace("first")
        second = self._attach_workspace("second")
        with self.assertRaises(ValidationError) as context:
            _club_workspace(self.club)
        self.assertEqual(
            context.exception.message_dict,
            {
                "union_workspace_id": [
                    "This Club belongs to multiple active Union workspaces. "
                    "Select one explicitly."
                ]
            },
        )
        self.assertEqual(_club_workspace(self.club, second.id), second)
        self.assertNotEqual(first, second)

    def test_unrelated_or_inactive_explicit_workspace_is_rejected(self):
        self._attach_workspace("eligible")
        unrelated_union = Union.objects.create(
            name="Unrelated Workspace Union",
            slug="unrelated-workspace-union",
        )
        unrelated = UnionWorkspace.objects.create(
            related_union=unrelated_union,
            name="Unrelated Workspace",
            slug="unrelated-workspace",
            acronym="UW",
            sport="Football",
        )
        with self.assertRaises(ValidationError):
            _club_workspace(self.club, unrelated.id)

        eligible = _club_workspace(self.club)
        eligible.status = UnionWorkspace.Status.INACTIVE
        eligible.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            _club_workspace(self.club, eligible.id)


class PlayerRegistrationSubmissionAPITests(APITestCase):
    list_url = "/api/teams/player-registration-submissions/"

    def setUp(self):
        self.union = Union.objects.create(name="API Union", slug="api-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="API Workspace",
            slug="api-workspace",
            acronym="API",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="API League",
            slug="api-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026/27",
            slug="2026-27",
        )
        self.other_season = Season.objects.create(
            league=self.league,
            name="2027/28",
            slug="2027-28",
        )
        self.actor = User.objects.create_user(
            email="api-club-admin@leagueos.test",
            password="StrongPass123!",
            role=User.Role.CLUB_ADMIN,
        )
        self.club = Club.objects.create(
            name="API Club",
            slug="api-club",
            admin=self.actor,
        )
        ClubAdminScope.objects.create(
            user=self.actor,
            club=self.club,
            role=ClubAdminScope.Role.CLUB_ADMIN,
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.season,
        )
        self.team = Team.objects.create(club=self.club, name="API First Team")

        self.other_actor = User.objects.create_user(
            email="other-club-admin@leagueos.test",
            password="StrongPass123!",
            role=User.Role.CLUB_ADMIN,
        )
        self.other_club = Club.objects.create(
            name="Other API Club",
            slug="other-api-club",
            admin=self.other_actor,
        )
        ClubAdminScope.objects.create(
            user=self.other_actor,
            club=self.other_club,
            role=ClubAdminScope.Role.CLUB_ADMIN,
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.other_club,
            season=self.season,
        )
        self.other_team = Team.objects.create(
            club=self.other_club,
            name="Other First Team",
        )

        self.edition = self._create_edition(
            union=self.union,
            league=self.league,
            season=self.season,
            suffix="current",
        )
        self.second_edition = self._create_edition(
            union=self.union,
            league=self.league,
            season=self.season,
            suffix="second",
        )
        self.wrong_season_edition = self._create_edition(
            union=self.union,
            league=self.league,
            season=self.other_season,
            suffix="wrong-season",
        )

        self.outside_union = Union.objects.create(
            name="Outside Union",
            slug="outside-union",
        )
        self.outside_workspace = UnionWorkspace.objects.create(
            related_union=self.outside_union,
            name="Outside Workspace",
            slug="outside-workspace",
            acronym="OUT",
            sport="Football",
        )
        self.outside_league = League.objects.create(
            union=self.outside_union,
            name="Outside League",
            slug="outside-league",
        )
        self.outside_season = Season.objects.create(
            league=self.outside_league,
            name="2026/27",
            slug="2026-27",
        )
        self.outside_edition = self._create_edition(
            union=self.outside_union,
            league=self.outside_league,
            season=self.outside_season,
            suffix="outside",
        )

        self.player_counter = 0
        self.submission = self._create_submission(registration_number="API-SUB-1")
        self.other_submission = self._create_submission(
            registration_number="API-OTHER-1",
            club=self.other_club,
            team=self.other_team,
        )
        self.legacy_registration = self._create_submission(
            registration_number="API-LEGACY-1",
            submission_status=PlayerRegistration.SubmissionStatus.LEGACY,
        )
        self.client.force_authenticate(self.actor)

    def _create_edition(self, *, union, league, season, suffix):
        identity = CompetitionIdentity.objects.create(
            union=union,
            primary_league=league,
            name=f"Competition {suffix}",
            slug=f"competition-{suffix}",
        )
        competition = Competition.objects.create(
            league=league,
            name=f"Competition {suffix} {season.name}",
            slug=f"competition-{suffix}-{season.slug}",
            season=season.name,
            season_record=season,
        )
        return CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=season,
        )

    def _create_submission(
        self,
        *,
        registration_number,
        club=None,
        team=None,
        submission_status=PlayerRegistration.SubmissionStatus.DRAFT,
    ):
        self.player_counter += 1
        player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number=f"API-P{self.player_counter:06d}",
            first_name="Amina",
            last_name="Nambassa",
            date_of_birth=date(2001, 5, 4),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        return PlayerRegistration.objects.create(
            club=club or self.club,
            team=team or self.team,
            registration_number=registration_number,
            first_name="Amina",
            last_name="Nambassa",
            date_of_birth=date(2001, 5, 4),
            nationality="Ugandan",
            position="MID",
            registered_date=date(2026, 7, 1),
            union_workspace=self.workspace,
            union_player=player,
            season_record=self.season,
            supporting_documents=["registration-form"],
            submission_status=submission_status,
        )

    def _create_registry_player(
        self,
        *,
        status_value=UnionPlayer.Status.APPROVED,
        first_name="Registry",
        last_name="Player",
        date_of_birth_value=date(1999, 2, 3),
        union=None,
        current_club=None,
    ):
        self.player_counter += 1
        player = UnionPlayer.objects.create(
            union=union or self.union,
            union_player_number=f"REG-P{self.player_counter:06d}",
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth_value,
            nationality="Ugandan",
            identity_reference=f"PRIVATE-{self.player_counter}",
            status=status_value,
            metadata={"private": True},
        )
        if current_club is not None:
            UnionPlayerRegistration.objects.create(
                workspace=self.workspace,
                player=player,
                club=current_club,
                season=self.season,
                status=UnionPlayerRegistration.Status.ACTIVE,
                effective_from=date(2026, 7, 1),
            )
        return player

    def _create_payload(self, registration_number="API-CREATE-1"):
        return {
            "club": self.club.id,
            "team": self.team.id,
            "registration_number": registration_number,
            "first_name": "Sarah",
            "last_name": "Akello",
            "date_of_birth": "2002-06-05",
            "nationality": "Ugandan",
            "position": "FW",
            "registered_date": "2026-07-01",
            "registration_type": (
                PlayerRegistration.RegistrationType.FIRST_REGISTRATION
            ),
            "season_record": self.season.id,
            "requested_competition_editions": [self.edition.id],
            "supporting_documents": ["registration-form"],
            "club_notes": "Ready for Union review.",
            "union_workspace_id": self.workspace.id,
        }

    def _detail_url(self, submission=None):
        return f"{self.list_url}{(submission or self.submission).id}/"

    def _action_url(self, action, submission=None):
        return f"{self._detail_url(submission)}{action}/"

    def _blocking_codes(self, submission):
        result = validate_player_registration_submission(
            submission=submission,
            actor=self.actor,
        )
        return result, {item["code"] for item in result["blocking_errors"]}

    def test_registry_search_is_union_scoped_and_privacy_safe(self):
        player = self._create_registry_player(
            first_name="Safe",
            last_name="Result",
            current_club=self.club,
        )
        outside = self._create_registry_player(
            first_name="Safe",
            last_name="Outside",
            union=self.outside_union,
        )
        response = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "q": "Safe"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data], [player.id])
        self.assertNotIn(outside.id, [row["id"] for row in response.data])
        self.assertEqual(
            set(response.data[0]),
            {
                "id",
                "union_player_number",
                "first_name",
                "last_name",
                "full_name",
                "date_of_birth",
                "nationality",
                "status",
                "can_be_selected",
                "selection_warning",
                "current_club_summary",
            },
        )
        self.assertEqual(
            response.data[0]["current_club_summary"],
            {"id": self.club.id, "name": self.club.name},
        )
        for sensitive_field in (
            "identity_reference",
            "metadata",
            "identity_verified_at",
            "identity_verified_by",
            "documents",
        ):
            self.assertNotIn(sensitive_field, response.data[0])

    def test_registry_search_denies_unassigned_or_unrelated_scope(self):
        unassigned = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.other_club.id, "q": "Player"},
        )
        self.assertEqual(unassigned.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("club", unassigned.data)

        unrelated_workspace = self.client.get(
            "/api/teams/player-registry-search/",
            {
                "club": self.club.id,
                "q": "Player",
                "union_workspace_id": self.outside_workspace.id,
            },
        )
        self.assertEqual(
            unrelated_workspace.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("union_workspace_id", unrelated_workspace.data)

    def test_registry_search_inputs_matching_and_limits(self):
        player = self._create_registry_player(
            first_name="Searchable",
            last_name="Identity",
            date_of_birth_value=date(1998, 4, 5),
        )
        search_values = (
            player.union_player_number.lower(),
            "searchable",
            "identity",
            "Searchable Identity",
        )
        for query in search_values:
            with self.subTest(query=query):
                response = self.client.get(
                    "/api/teams/player-registry-search/",
                    {"club": self.club.id, "q": query},
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn(player.id, [row["id"] for row in response.data])

        by_date = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "date_of_birth": "1998-04-05"},
        )
        self.assertEqual(by_date.status_code, status.HTTP_200_OK)
        self.assertIn(player.id, [row["id"] for row in by_date.data])

        missing = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "q": "   "},
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        for index in range(4):
            self._create_registry_player(
                first_name="Limited",
                last_name=f"Result{index}",
            )
        limited = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "q": "Limited", "limit": 2},
        )
        self.assertEqual(limited.status_code, status.HTTP_200_OK)
        self.assertEqual(len(limited.data), 2)
        over_limit = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "q": "Limited", "limit": 51},
        )
        self.assertEqual(over_limit.status_code, status.HTTP_400_BAD_REQUEST)

        direct_results = search_union_players_for_club(
            actor=self.actor,
            club=self.club,
            query="Limited",
            limit=3,
        )
        self.assertEqual(len(direct_results), 3)
        with self.assertRaises(ValidationError):
            search_union_players_for_club(
                actor=self.actor,
                club=self.club,
                query="Limited",
                limit=51,
            )

    def test_registry_search_status_selectability(self):
        statuses = (
            UnionPlayer.Status.APPROVED,
            UnionPlayer.Status.PROVISIONAL,
            UnionPlayer.Status.PENDING_VERIFICATION,
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        )
        for player_status in statuses:
            self._create_registry_player(
                status_value=player_status,
                first_name="StatusProbe",
                last_name=player_status,
            )
        response = self.client.get(
            "/api/teams/player-registry-search/",
            {"club": self.club.id, "q": "StatusProbe"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = {row["status"]: row for row in response.data}
        self.assertTrue(results[UnionPlayer.Status.APPROVED]["can_be_selected"])
        self.assertIsNone(results[UnionPlayer.Status.APPROVED]["selection_warning"])
        for selectable_status in (
            UnionPlayer.Status.PROVISIONAL,
            UnionPlayer.Status.PENDING_VERIFICATION,
        ):
            self.assertTrue(results[selectable_status]["can_be_selected"])
            self.assertTrue(results[selectable_status]["selection_warning"])
        for blocked_status in (
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        ):
            self.assertFalse(results[blocked_status]["can_be_selected"])
            self.assertTrue(results[blocked_status]["selection_warning"])

    def test_structured_validation_accepts_a_maintained_submission(self):
        self.submission.requested_competition_editions.set([self.edition])
        result, blocking_codes = self._blocking_codes(self.submission)
        self.assertEqual(blocking_codes, set())
        self.assertEqual(result["version"], 1)
        self.assertTrue(result["evaluated_at"])
        passed_codes = {item["code"] for item in result["passed_checks"]}
        self.assertTrue(
            {
                "CLUB_SCOPE_VALID",
                "WORKSPACE_VALID",
                "TEAM_CLUB_VALID",
                "SEASON_VALID",
                "DOCUMENTS_PRESENT",
                "PLAYER_IDENTITY_VALID",
                "COMPETITION_EDITIONS_VALID",
                "REGISTRATION_DATES_VALID",
            }.issubset(passed_codes)
        )
        for bucket in (
            "blocking_errors",
            "review_warnings",
            "passed_checks",
            "capability_notes",
        ):
            for item in result[bucket]:
                self.assertEqual(
                    set(item),
                    {"code", "field", "message", "severity"},
                )

    def test_structured_validation_reports_all_maintained_blocking_rules(self):
        lost_scope_result = validate_player_registration_submission(
            submission=self.submission,
            actor=self.other_actor,
        )
        self.assertIn(
            "CLUB_SCOPE_INVALID",
            {item["code"] for item in lost_scope_result["blocking_errors"]},
        )

        invalid_workspace = self._create_submission(
            registration_number="VALIDATE-WORKSPACE"
        )
        invalid_workspace.union_workspace = self.outside_workspace
        invalid_workspace.save(update_fields=["union_workspace"])
        self.assertIn(
            "WORKSPACE_INVALID",
            self._blocking_codes(invalid_workspace)[1],
        )

        missing_season = self._create_submission(
            registration_number="VALIDATE-NO-SEASON"
        )
        missing_season.season_record = None
        missing_season.save(update_fields=["season_record"])
        self.assertIn("SEASON_REQUIRED", self._blocking_codes(missing_season)[1])

        missing_documents = self._create_submission(
            registration_number="VALIDATE-NO-DOCS"
        )
        missing_documents.supporting_documents = ["", "   "]
        missing_documents.save(update_fields=["supporting_documents"])
        self.assertIn(
            "SUPPORTING_DOCUMENTS_REQUIRED",
            self._blocking_codes(missing_documents)[1],
        )

        wrong_team = self._create_submission(registration_number="VALIDATE-WRONG-TEAM")
        wrong_team.team = self.other_team
        wrong_team.save(update_fields=["team"])
        self.assertIn("TEAM_CLUB_INVALID", self._blocking_codes(wrong_team)[1])

        wrong_season = self._create_submission(
            registration_number="VALIDATE-WRONG-SEASON"
        )
        wrong_season.season_record = self.outside_season
        wrong_season.save(update_fields=["season_record"])
        self.assertIn("SEASON_UNION_INVALID", self._blocking_codes(wrong_season)[1])

        wrong_union_player = self._create_registry_player(union=self.outside_union)
        wrong_player = self._create_submission(
            registration_number="VALIDATE-WRONG-PLAYER"
        )
        wrong_player.union_player = wrong_union_player
        wrong_player.save(update_fields=["union_player"])
        self.assertIn("PLAYER_UNION_INVALID", self._blocking_codes(wrong_player)[1])

        missing_player = self._create_submission(
            registration_number="VALIDATE-NO-PLAYER"
        )
        missing_player.union_player = None
        missing_player.save(update_fields=["union_player"])
        self.assertIn(
            "PLAYER_IDENTITY_REQUIRED",
            self._blocking_codes(missing_player)[1],
        )

        for player_status in (
            UnionPlayer.Status.SUSPENDED,
            UnionPlayer.Status.REJECTED,
            UnionPlayer.Status.ARCHIVED,
        ):
            with self.subTest(player_status=player_status):
                submission = self._create_submission(
                    registration_number=f"VALIDATE-{player_status}"
                )
                submission.union_player.status = player_status
                submission.union_player.save(update_fields=["status"])
                self.assertIn(
                    f"PLAYER_{player_status}",
                    self._blocking_codes(submission)[1],
                )

        wrong_union_edition = self._create_submission(
            registration_number="VALIDATE-WRONG-EDITION-UNION"
        )
        wrong_union_edition.requested_competition_editions.set([self.outside_edition])
        self.assertIn(
            "COMPETITION_EDITION_UNION_INVALID",
            self._blocking_codes(wrong_union_edition)[1],
        )

        wrong_season_edition = self._create_submission(
            registration_number="VALIDATE-WRONG-EDITION-SEASON"
        )
        wrong_season_edition.requested_competition_editions.set(
            [self.wrong_season_edition]
        )
        self.assertIn(
            "COMPETITION_EDITION_SEASON_INVALID",
            self._blocking_codes(wrong_season_edition)[1],
        )

        invalid_dates = self._create_submission(registration_number="VALIDATE-DATES")
        invalid_dates.expiry_date = date(2026, 6, 30)
        invalid_dates.save(update_fields=["expiry_date"])
        self.assertIn(
            "REGISTRATION_DATE_ORDER_INVALID",
            self._blocking_codes(invalid_dates)[1],
        )

        invalid_registration_type = self._create_submission(
            registration_number="VALIDATE-REGISTRATION-TYPE"
        )
        invalid_registration_type.registration_type = "UNSUPPORTED"
        invalid_registration_type.save(update_fields=["registration_type"])
        self.assertIn(
            "REGISTRATION_TYPE_INVALID",
            self._blocking_codes(invalid_registration_type)[1],
        )

        duplicate = self._create_submission(
            registration_number="VALIDATE-DUPLICATE-PENDING"
        )
        duplicate.union_player = self.submission.union_player
        duplicate.save(update_fields=["union_player"])
        self.assertIn(
            "DUPLICATE_PENDING_SUBMISSION",
            self._blocking_codes(duplicate)[1],
        )

        case_duplicate = self._create_submission(registration_number="api-sub-1")
        self.assertIn(
            "DUPLICATE_REGISTRATION_NUMBER",
            self._blocking_codes(case_duplicate)[1],
        )

    def test_structured_validation_reports_warnings_and_capability_limits(self):
        provisional = self._create_submission(registration_number="VALIDATE-WARNINGS")
        provisional.union_player.status = UnionPlayer.Status.PROVISIONAL
        provisional.union_player.save(update_fields=["status"])
        provisional.registration_type = (
            PlayerRegistration.RegistrationType.DUAL_REGISTRATION
        )
        provisional.save(update_fields=["registration_type"])
        UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=provisional.union_player,
            club=self.club,
            season=self.season,
            status=UnionPlayerRegistration.Status.APPROVED,
            effective_from=date(2025, 7, 1),
        )
        result = validate_player_registration_submission(
            submission=provisional,
            actor=self.actor,
        )
        warning_codes = {item["code"] for item in result["review_warnings"]}
        self.assertTrue(
            {
                "PLAYER_IDENTITY_PROVISIONAL",
                "PLAYER_HAS_REGISTRATION_HISTORY",
                "NO_COMPETITION_EDITION_REQUESTED",
                "DUAL_REGISTRATION_RULES_LIMITED",
            }.issubset(warning_codes)
        )
        capability_codes = {item["code"] for item in result["capability_notes"]}
        self.assertIn("REGISTRATION_FEE_CHECK_UNAVAILABLE", capability_codes)
        self.assertEqual(len(capability_codes), len(result["capability_notes"]))

        pending = self._create_submission(
            registration_number="VALIDATE-PENDING-WARNING"
        )
        pending.union_player.status = UnionPlayer.Status.PENDING_VERIFICATION
        pending.union_player.save(update_fields=["status"])
        pending_result = validate_player_registration_submission(
            submission=pending,
            actor=self.actor,
        )
        self.assertIn(
            "PLAYER_IDENTITY_PENDING_VERIFICATION",
            {item["code"] for item in pending_result["review_warnings"]},
        )

    def test_legacy_list_remains_club_scoped_and_includes_workflow_status(self):
        response = self.client.get("/api/teams/players/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["id"] for row in response.data}
        self.assertIn(self.submission.id, returned_ids)
        self.assertIn(self.legacy_registration.id, returned_ids)
        self.assertNotIn(self.other_submission.id, returned_ids)
        for row in response.data:
            self.assertIn("submission_status", row)

    def test_legacy_post_creates_an_inactive_draft_with_compatibility_marker(self):
        response = self.client.post(
            "/api/teams/players/",
            self._create_payload("LEGACY-COMPAT-CREATE"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["workflow"],
            "PLAYER_REGISTRATION_SUBMISSION",
        )
        self.assertTrue(response.data["deprecated_direct_creation"])
        draft = PlayerRegistration.objects.get(pk=response.data["submission"]["id"])
        self.assertEqual(
            draft.submission_status,
            PlayerRegistration.SubmissionStatus.DRAFT,
        )
        self.assertEqual(
            draft.status,
            PlayerRegistration.RegistrationStatus.INACTIVE,
        )
        self.assertFalse(
            UnionPlayerRegistration.objects.filter(source_registration=draft).exists()
        )
        audit_event = UnionAuditEvent.objects.get(
            action="player_registration.draft_created",
            target_id=draft.id,
        )
        self.assertEqual(
            audit_event.metadata,
            {"source_route": "legacy_players_post"},
        )

    def test_legacy_post_rejects_all_client_controlled_fields(self):
        controlled_fields = {
            "status": PlayerRegistration.RegistrationStatus.ACTIVE,
            "submission_status": PlayerRegistration.SubmissionStatus.APPROVED,
            "user": self.actor.id,
            "union_workspace": self.workspace.id,
            "union_player": self.submission.union_player_id,
            "submitted_by": self.actor.id,
            "assigned_reviewer": self.actor.id,
            "change_request_reason": "Client decision",
            "union_decision_reason": "Client decision",
            "reviewed_at": timezone.now().isoformat(),
            "automatic_validation": {"passed": True},
            "submission_revision": 99,
        }
        for index, (field, value) in enumerate(
            controlled_fields.items(),
            start=1,
        ):
            with self.subTest(field=field):
                payload = self._create_payload(f"LEGACY-CONTROLLED-{index}")
                payload[field] = value
                response = self.client.post(
                    "/api/teams/players/",
                    payload,
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn(field, response.data)

    def test_legacy_detail_get_is_safe_and_conceals_other_clubs(self):
        legacy_response = self.client.get(
            f"/api/teams/players/{self.legacy_registration.id}/"
        )
        self.assertEqual(legacy_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            legacy_response.data["submission_status"],
            PlayerRegistration.SubmissionStatus.LEGACY,
        )
        self.assertIn("status", legacy_response.data)
        for private_field in (
            "user",
            "union_workspace",
            "union_player",
            "submitted_by",
            "assigned_reviewer",
            "union_decision_reason",
            "automatic_validation",
        ):
            self.assertNotIn(private_field, legacy_response.data)

        submission_response = self.client.get(
            f"/api/teams/players/{self.submission.id}/"
        )
        self.assertEqual(submission_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submission_response.data["id"], self.submission.id)
        self.assertNotIn("assigned_reviewer", submission_response.data)
        self.assertEqual(
            self.client.get(
                f"/api/teams/players/{self.other_submission.id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_legacy_detail_patch_routes_by_record_type(self):
        draft_response = self.client.patch(
            f"/api/teams/players/{self.submission.id}/",
            {"position": "FW"},
            format="json",
        )
        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.position, "FW")

        changes_requested = self._create_submission(
            registration_number="LEGACY-PATCH-CHANGES"
        )
        changes_requested.submission_status = (
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        )
        changes_requested.save(update_fields=["submission_status"])
        changed = self.client.patch(
            f"/api/teams/players/{changes_requested.id}/",
            {"club_notes": "Corrected by Club."},
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)

        for blocked_status in (
            PlayerRegistration.SubmissionStatus.SUBMITTED,
            PlayerRegistration.SubmissionStatus.APPROVED,
        ):
            with self.subTest(blocked_status=blocked_status):
                blocked = self._create_submission(
                    registration_number=f"LEGACY-PATCH-{blocked_status}"
                )
                blocked.submission_status = blocked_status
                blocked.save(update_fields=["submission_status"])
                response = self.client.patch(
                    f"/api/teams/players/{blocked.id}/",
                    {"position": "GK"},
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

    def test_legacy_roster_patch_allows_only_safe_fields(self):
        response = self.client.patch(
            f"/api/teams/players/{self.legacy_registration.id}/",
            {
                "position": "DF",
                "metadata": {"roster_note": "Updated"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.legacy_registration.refresh_from_db()
        self.assertEqual(self.legacy_registration.position, "DF")
        self.assertEqual(
            self.legacy_registration.metadata,
            {"roster_note": "Updated"},
        )
        self.assertEqual(
            self.legacy_registration.submission_status,
            PlayerRegistration.SubmissionStatus.LEGACY,
        )

        controlled_fields = {
            "status": PlayerRegistration.RegistrationStatus.SUSPENDED,
            "club": self.other_club.id,
            "registration_number": "CLIENT-CHANGED",
        }
        for field, value in controlled_fields.items():
            with self.subTest(field=field):
                rejected = self.client.patch(
                    f"/api/teams/players/{self.legacy_registration.id}/",
                    {field: value},
                    format="json",
                )
                self.assertEqual(
                    rejected.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn(field, rejected.data)

        wrong_team = self.client.patch(
            f"/api/teams/players/{self.legacy_registration.id}/",
            {"team": self.other_team.id},
            format="json",
        )
        self.assertEqual(wrong_team.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", wrong_team.data)

    def test_legacy_detail_put_and_delete_are_disabled_without_deletion(self):
        url = f"/api/teams/players/{self.legacy_registration.id}/"
        self.assertEqual(
            self.client.put(url, {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(url).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertTrue(
            PlayerRegistration.objects.filter(pk=self.legacy_registration.id).exists()
        )

    def test_list_is_club_scoped_filterable_and_searchable(self):
        submitted = self._create_submission(
            registration_number="SEARCH-ME-99",
            submission_status=PlayerRegistration.SubmissionStatus.SUBMITTED,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response.data},
            {self.submission.id, submitted.id},
        )

        filtered = self.client.get(
            self.list_url,
            {"submission_status": PlayerRegistration.SubmissionStatus.SUBMITTED},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in filtered.data], [submitted.id])

        for search in ("SEARCH-ME", "Amina", "Nambassa"):
            with self.subTest(search=search):
                searched = self.client.get(self.list_url, {"search": search})
                self.assertEqual(searched.status_code, status.HTTP_200_OK)
                self.assertIn(submitted.id, [row["id"] for row in searched.data])

    def test_create_returns_explicit_detail_and_rejects_controlled_fields(self):
        response = self.client.post(
            self.list_url,
            self._create_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = PlayerRegistration.objects.get(pk=response.data["id"])
        self.assertEqual(
            created.submission_status,
            PlayerRegistration.SubmissionStatus.DRAFT,
        )
        self.assertEqual(
            list(created.requested_competition_editions.values_list("id", flat=True)),
            [self.edition.id],
        )
        self.assertNotIn("identity_reference", response.data)
        self.assertNotIn("assigned_reviewer", response.data)

        protected_fields = {
            "submission_status": PlayerRegistration.SubmissionStatus.APPROVED,
            "status": PlayerRegistration.RegistrationStatus.SUSPENDED,
            "assigned_reviewer": self.actor.id,
        }
        for index, (field, value) in enumerate(protected_fields.items(), start=1):
            with self.subTest(field=field):
                payload = self._create_payload(f"API-PROTECTED-{index}")
                payload[field] = value
                rejected = self.client.post(self.list_url, payload, format="json")
                self.assertEqual(
                    rejected.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn(field, rejected.data)

    def test_detail_is_concealed_and_put_and_delete_are_disabled(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.submission.id)
        for hidden_field in (
            "identity_reference",
            "union_workspace",
            "assigned_reviewer",
            "automatic_validation",
            "metadata",
        ):
            self.assertNotIn(hidden_field, response.data)

        concealed = self.client.get(self._detail_url(self.other_submission))
        self.assertEqual(concealed.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(self._detail_url(self.legacy_registration)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.put(self._detail_url(), {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(self._detail_url()).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_patch_updates_draft_and_rejects_club_or_submitted_updates(self):
        response = self.client.patch(
            self._detail_url(),
            {"position": "FW", "club_notes": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.position, "FW")
        self.assertEqual(self.submission.club_notes, "Updated")

        club_change = self.client.patch(
            self._detail_url(),
            {"club": self.other_club.id},
            format="json",
        )
        self.assertEqual(club_change.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("club", club_change.data)

        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.SUBMITTED
        )
        self.submission.save(update_fields=["submission_status"])
        submitted_update = self.client.patch(
            self._detail_url(),
            {"position": "GK"},
            format="json",
        )
        self.assertEqual(
            submitted_update.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_patch_updates_clears_and_validates_requested_editions(self):
        response = self.client.patch(
            self._detail_url(),
            {
                "requested_competition_editions": [
                    self.edition.id,
                    self.second_edition.id,
                    self.edition.id,
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data["requested_competition_editions"]),
            {self.edition.id, self.second_edition.id},
        )

        cleared = self.client.patch(
            self._detail_url(),
            {"requested_competition_editions": []},
            format="json",
        )
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertEqual(cleared.data["requested_competition_editions"], [])

        for edition in (self.outside_edition, self.wrong_season_edition):
            with self.subTest(edition=edition.id):
                rejected = self.client.patch(
                    self._detail_url(),
                    {"requested_competition_editions": [edition.id]},
                    format="json",
                )
                self.assertEqual(
                    rejected.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn("requested_competition_editions", rejected.data)

        self.submission.requested_competition_editions.set([self.edition])
        wrong_season = self.client.patch(
            self._detail_url(),
            {"season_record": self.other_season.id},
            format="json",
        )
        self.assertEqual(wrong_season.status_code, status.HTTP_400_BAD_REQUEST)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.season_record, self.season)

    def test_submit_and_resubmit_routes_enforce_transitions_and_timestamps(self):
        submitted = self.client.post(self._action_url("submit"), {}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertEqual(
            submitted.data["submission_status"],
            PlayerRegistration.SubmissionStatus.SUBMITTED,
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.automatic_validation["version"], 1)
        self.assertEqual(
            self.submission.automatic_validation["blocking_errors"],
            [],
        )
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                workspace=self.workspace,
                action="player_registration.validation_completed",
                target_id=self.submission.id,
            ).exists()
        )
        repeated = self.client.post(self._action_url("submit"), {}, format="json")
        self.assertEqual(repeated.status_code, status.HTTP_400_BAD_REQUEST)

        resubmission = self._create_submission(registration_number="API-RESUBMIT-1")
        illegal = self.client.post(
            self._action_url("resubmit", resubmission),
            {},
            format="json",
        )
        self.assertEqual(illegal.status_code, status.HTTP_400_BAD_REQUEST)

        original_submitted_at = timezone.now()
        resubmission.submission_status = (
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        )
        resubmission.submitted_at = original_submitted_at
        resubmission.submission_revision = 1
        resubmission.automatic_validation = {
            "version": 0,
            "evaluated_at": "stale",
        }
        resubmission.save(
            update_fields=[
                "submission_status",
                "submitted_at",
                "submission_revision",
                "automatic_validation",
            ]
        )
        response = self.client.post(
            self._action_url("resubmit", resubmission),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resubmission.refresh_from_db()
        self.assertEqual(resubmission.submitted_at, original_submitted_at)
        self.assertIsNotNone(resubmission.last_resubmitted_at)
        self.assertEqual(resubmission.submission_revision, 2)
        self.assertEqual(resubmission.automatic_validation["version"], 1)
        self.assertNotEqual(
            resubmission.automatic_validation["evaluated_at"],
            "stale",
        )

    def test_blocked_submit_persists_validation_without_transition(self):
        self.submission.supporting_documents = []
        self.submission.save(update_fields=["supporting_documents"])
        response = self.client.post(self._action_url("submit"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            ["Player registration submission contains blocking validation errors."],
        )
        self.assertIn("automatic_validation", response.data)
        self.assertIn(
            "SUPPORTING_DOCUMENTS_REQUIRED",
            {
                item["code"]
                for item in response.data["automatic_validation"]["blocking_errors"]
            },
        )
        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.submission_status,
            PlayerRegistration.SubmissionStatus.DRAFT,
        )
        self.assertEqual(self.submission.submission_revision, 0)
        self.assertIsNone(self.submission.submitted_at)
        self.assertEqual(self.submission.automatic_validation["version"], 1)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                action="player_registration.validation_completed",
                target_id=self.submission.id,
            ).exists()
        )
        self.assertFalse(
            UnionAuditEvent.objects.filter(
                action="player_registration.submitted",
                target_id=self.submission.id,
            ).exists()
        )

    def test_blocked_resubmit_stays_change_requested_and_replaces_old_validation(
        self,
    ):
        original_submitted_at = timezone.now()
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        )
        self.submission.submitted_at = original_submitted_at
        self.submission.submission_revision = 3
        self.submission.supporting_documents = []
        self.submission.automatic_validation = {
            "version": 0,
            "evaluated_at": "old-result",
        }
        self.submission.save()

        response = self.client.post(
            self._action_url("resubmit"),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.submission_status,
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED,
        )
        self.assertEqual(self.submission.submission_revision, 3)
        self.assertEqual(self.submission.submitted_at, original_submitted_at)
        self.assertIsNone(self.submission.last_resubmitted_at)
        self.assertEqual(self.submission.automatic_validation["version"], 1)
        self.assertNotEqual(
            self.submission.automatic_validation["evaluated_at"],
            "old-result",
        )

    def test_withdraw_requires_reason_and_enforces_legal_states(self):
        blank_submission = self._create_submission(
            registration_number="API-WITHDRAW-BLANK"
        )
        blank = self.client.post(
            self._action_url("withdraw", blank_submission),
            {"withdrawal_reason": "   "},
            format="json",
        )
        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self._action_url("withdraw"),
            {"withdrawal_reason": "Player chose another pathway."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["submission_status"],
            PlayerRegistration.SubmissionStatus.WITHDRAWN,
        )
        repeated = self.client.post(
            self._action_url("withdraw"),
            {"withdrawal_reason": "Try again."},
            format="json",
        )
        self.assertEqual(repeated.status_code, status.HTTP_400_BAD_REQUEST)

        approved = self._create_submission(
            registration_number="API-WITHDRAW-APPROVED",
            submission_status=PlayerRegistration.SubmissionStatus.APPROVED,
        )
        rejected = self.client.post(
            self._action_url("withdraw", approved),
            {"withdrawal_reason": "Too late."},
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_decision_response_is_explicit_and_club_scoped(self):
        self.submission.submission_status = (
            PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
        )
        self.submission.change_request_reason = "Correct the date evidence."
        self.submission.union_decision_reason = "Identity evidence did not match."
        self.submission.reviewed_at = timezone.now()
        self.submission.automatic_validation = {"internal_rule": "failed"}
        self.submission.save()
        self.submission.requested_competition_editions.set([self.edition])

        response = self.client.get(self._action_url("decision"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {
                "id",
                "submission_status",
                "change_request_reason",
                "union_decision_reason",
                "reviewed_at",
                "submission_revision",
                "automatic_validation",
                "requested_competition_editions",
            },
        )
        self.assertEqual(
            response.data["change_request_reason"],
            "Correct the date evidence.",
        )
        for hidden_field in (
            "identity_reference",
            "assigned_reviewer",
            "union_workspace",
            "submitted_by",
        ):
            self.assertNotIn(hidden_field, response.data)

        concealed = self.client.get(self._action_url("decision", self.other_submission))
        self.assertEqual(concealed.status_code, status.HTTP_404_NOT_FOUND)
