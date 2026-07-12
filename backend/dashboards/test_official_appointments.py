from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, User
from accounts.models import AuditLog
from .models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueAdminScope,
    Match,
    Union,
    UnionMatchOfficial,
)


class SharedOfficialAppointmentWorkflowTests(APITestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Uganda Test Rugby Union",
            slug="uganda-test-rugby-union",
        )
        self.other_union = Union.objects.create(
            name="Uganda Test Football Union",
            slug="uganda-test-football-union",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Test Premiership",
            slug="test-premiership",
        )
        self.other_league = League.objects.create(
            union=self.other_union,
            name="Other Premier League",
            slug="other-premier-league",
        )
        self.competition = Competition.objects.create(
            league=self.league,
            name="Test Premiership 2026",
            slug="test-premiership-2026",
            season="2026",
        )
        self.second_competition = Competition.objects.create(
            league=self.league,
            name="Test Cup 2026",
            slug="test-cup-2026",
            season="2026",
        )
        self.other_competition = Competition.objects.create(
            league=self.other_league,
            name="Other Competition 2026",
            slug="other-competition-2026",
            season="2026",
        )

        self.home = Club.objects.create(
            name="Appointment Home Club",
            slug="appointment-home-club",
            sport=Club.Sport.RUGBY,
        )
        self.away = Club.objects.create(
            name="Appointment Away Club",
            slug="appointment-away-club",
            sport=Club.Sport.RUGBY,
        )
        self.other_home = Club.objects.create(
            name="Other Appointment Home Club",
            slug="other-appointment-home-club",
            sport=Club.Sport.FOOTBALL,
        )
        self.other_away = Club.objects.create(
            name="Other Appointment Away Club",
            slug="other-appointment-away-club",
            sport=Club.Sport.FOOTBALL,
        )

        self.match = Match.objects.create(
            competition=self.competition,
            home_club=self.home,
            away_club=self.away,
            match_date=timezone.now() + timedelta(days=7),
            venue="Test Stadium",
        )
        self.second_match = Match.objects.create(
            competition=self.second_competition,
            home_club=self.home,
            away_club=self.away,
            match_date=timezone.now() + timedelta(days=14),
            venue="Cup Stadium",
        )
        self.other_match = Match.objects.create(
            competition=self.other_competition,
            home_club=self.other_home,
            away_club=self.other_away,
            match_date=timezone.now() + timedelta(days=10),
            venue="Other Stadium",
        )

        self.league_admin = User.objects.create_user(
            email="league-admin-appointments@example.com",
            password="StrongPass123!",
            role=User.Role.LEAGUE_ADMIN,
        )
        self.competition_admin = User.objects.create_user(
            email="competition-admin-appointments@example.com",
            password="StrongPass123!",
            role=User.Role.LEAGUE_ADMIN,
        )
        self.official_user = User.objects.create_user(
            email="official-appointments@example.com",
            password="StrongPass123!",
            role=User.Role.REFEREE,
        )
        self.other_official_user = User.objects.create_user(
            email="other-official-appointments@example.com",
            password="StrongPass123!",
            role=User.Role.REFEREE,
        )

        LeagueAdminScope.objects.create(
            user=self.league_admin,
            league=self.league,
            role=LeagueAdminScope.Role.LEAGUE_ADMIN,
        )
        LeagueAdminScope.objects.create(
            user=self.competition_admin,
            league=self.league,
            competition=self.competition,
            role=LeagueAdminScope.Role.COMPETITION_ADMIN,
        )

        self.official = UnionMatchOfficial.objects.create(
            union=self.union,
            user=self.official_user,
            full_name="Primary Test Official",
            email=self.official_user.email,
            primary_sport=UnionMatchOfficial.SportType.RUGBY,
            role_type=UnionMatchOfficial.RoleType.CENTRE_REFEREE,
            status=UnionMatchOfficial.Status.AVAILABLE,
        )
        self.other_official = UnionMatchOfficial.objects.create(
            union=self.union,
            user=self.other_official_user,
            full_name="Other Test Official",
            email=self.other_official_user.email,
            primary_sport=UnionMatchOfficial.SportType.RUGBY,
            role_type=UnionMatchOfficial.RoleType.ASSISTANT_REFEREE,
            status=UnionMatchOfficial.Status.AVAILABLE,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def appointment_payload(self, match=None, official=None):
        return {
            "match": (match or self.match).id,
            "official": (official or self.official).id,
            "role_type": UnionMatchOfficial.RoleType.CENTRE_REFEREE,
            "status": FixtureOfficialAssignment.Status.ASSIGNED,
            "notes": "Report 45 minutes before kickoff.",
        }

    def test_league_admin_can_assign_union_official_to_own_league(self):
        self.authenticate(self.league_admin)

        response = self.client.post(
            "/api/dashboards/league-admin/fixture-official-appointments/",
            self.appointment_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["league"], self.league.id)
        self.assertEqual(response.data["competition"], self.competition.id)
        self.assertEqual(response.data["status"], "ASSIGNED")
        self.assertEqual(response.data["official"], self.official.id)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.league_admin,
                action="league_fixture_official_assigned",
            ).exists()
        )

    def test_league_admin_cannot_assign_outside_scope(self):
        self.authenticate(self.league_admin)

        response = self.client.post(
            "/api/dashboards/league-admin/fixture-official-appointments/",
            self.appointment_payload(match=self.other_match),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            FixtureOfficialAssignment.objects.filter(match=self.other_match).exists()
        )

    def test_competition_admin_is_limited_to_selected_competition(self):
        self.authenticate(self.competition_admin)

        allowed = self.client.post(
            "/api/dashboards/league-admin/fixture-official-appointments/",
            self.appointment_payload(),
            format="json",
        )
        denied = self.client.post(
            "/api/dashboards/league-admin/fixture-official-appointments/",
            self.appointment_payload(match=self.second_match),
            format="json",
        )

        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_official_can_only_view_and_accept_own_appointment(self):
        own_assignment = FixtureOfficialAssignment.objects.create(
            match=self.match,
            official=self.official,
            role_type=UnionMatchOfficial.RoleType.CENTRE_REFEREE,
            status=FixtureOfficialAssignment.Status.ASSIGNED,
            assigned_by=self.league_admin,
        )
        other_assignment = FixtureOfficialAssignment.objects.create(
            match=self.second_match,
            official=self.other_official,
            role_type=UnionMatchOfficial.RoleType.ASSISTANT_REFEREE,
            status=FixtureOfficialAssignment.Status.ASSIGNED,
            assigned_by=self.league_admin,
        )
        self.authenticate(self.official_user)

        listing = self.client.get("/api/dashboards/match-official/appointments/")
        accepted = self.client.patch(
            f"/api/dashboards/match-official/appointments/{own_assignment.id}/response/",
            {"status": "ACCEPTED"},
            format="json",
        )
        forbidden = self.client.patch(
            f"/api/dashboards/match-official/appointments/{other_assignment.id}/response/",
            {"status": "ACCEPTED"},
            format="json",
        )

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["id"], own_assignment.id)
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data["status"], "ACCEPTED")
        self.assertIsNotNone(accepted.data["responded_at"])
        self.assertEqual(forbidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_declining_requires_a_reason(self):
        assignment = FixtureOfficialAssignment.objects.create(
            match=self.match,
            official=self.official,
            role_type=UnionMatchOfficial.RoleType.CENTRE_REFEREE,
            status=FixtureOfficialAssignment.Status.PROPOSED,
            assigned_by=self.league_admin,
        )
        self.authenticate(self.official_user)

        missing_reason = self.client.patch(
            f"/api/dashboards/match-official/appointments/{assignment.id}/response/",
            {"status": "DECLINED"},
            format="json",
        )
        declined = self.client.patch(
            f"/api/dashboards/match-official/appointments/{assignment.id}/response/",
            {
                "status": "DECLINED",
                "response_note": "Already appointed to another match.",
            },
            format="json",
        )

        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(declined.status_code, status.HTTP_200_OK)
        self.assertEqual(declined.data["status"], "DECLINED")
        self.assertEqual(
            declined.data["response_note"],
            "Already appointed to another match.",
        )

    def test_league_admin_cannot_forge_official_response(self):
        assignment = FixtureOfficialAssignment.objects.create(
            match=self.match,
            official=self.official,
            role_type=UnionMatchOfficial.RoleType.CENTRE_REFEREE,
            status=FixtureOfficialAssignment.Status.ASSIGNED,
            assigned_by=self.league_admin,
        )
        self.authenticate(self.league_admin)

        response = self.client.patch(
            f"/api/dashboards/league-admin/fixture-official-appointments/{assignment.id}/",
            {"status": "ACCEPTED"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "ASSIGNED")
