from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, ClubAdminScope, User
from dashboards.models import (
    ClubAffiliation,
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    League,
    Season,
    Union,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
)
from dashboards.union_player_transfer_services import (
    create_player_transfer_draft,
    submit_player_transfer,
)

from .models import Team


class ClubPlayerTransferSubmissionAPITests(APITestCase):
    list_url = "/api/teams/player-transfer-submissions/"

    def setUp(self):
        self.union = Union.objects.create(
            name="Transfer API Union", slug="transfer-api"
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Transfer API Workspace",
            slug="transfer-api-workspace",
            acronym="TAW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Transfer API League",
            slug="transfer-api-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026",
            slug="transfer-api-2026",
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
        self.unrelated_actor = self._user("unrelated", User.Role.CLUB_ADMIN)
        self.source_club = self._club(
            "Source",
            self.source_actor,
            ClubAdminScope.Role.CHAIRMAN,
        )
        self.destination_club = self._club(
            "Destination",
            self.destination_actor,
            ClubAdminScope.Role.CHAIRMAN,
        )
        self.no_permission_club = self._club(
            "No Permission",
            self.no_permission_actor,
            ClubAdminScope.Role.CLUB_ADMIN,
        )
        self.unrelated_club = self._club(
            "Unrelated",
            self.unrelated_actor,
            ClubAdminScope.Role.CHAIRMAN,
        )
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Source API Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Destination API Team",
        )
        self.no_permission_team = Team.objects.create(
            club=self.no_permission_club,
            name="No Permission API Team",
        )
        self.unrelated_team = Team.objects.create(
            club=self.unrelated_club,
            name="Unrelated API Team",
        )
        for club in (
            self.source_club,
            self.destination_club,
            self.no_permission_club,
        ):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.player = UnionPlayer.objects.create(
            union=self.union,
            user=self.player_user,
            union_player_number="TA-P000001",
            first_name="Martha",
            last_name="Auma",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            identity_reference="PRIVATE-IDENTITY",
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
        )
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Transfer API Cup",
            slug="transfer-api-cup",
        )
        competition = Competition.objects.create(
            league=self.league,
            name="Transfer API Competition",
            slug="transfer-api-competition",
            season="2026",
            season_record=self.season,
        )
        edition = CompetitionEdition.objects.create(
            identity=identity,
            competition=competition,
            season=self.season,
        )
        UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            club=self.source_club,
            team=self.source_team,
            competition_identity=identity,
            competition_edition=edition,
            season=self.season,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        outside_union = Union.objects.create(
            name="Outside Transfer Union",
            slug="outside-transfer-union",
        )
        self.outside_workspace = UnionWorkspace.objects.create(
            related_union=outside_union,
            name="Outside Transfer Workspace",
            slug="outside-transfer-workspace",
            acronym="OTW",
            sport="Football",
        )
        self.client.force_authenticate(self.destination_actor)

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}@transfer-api.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin, role):
        club = Club.objects.create(
            name=f"{prefix} Transfer API Club",
            slug=f"{prefix.lower().replace(' ', '-')}-transfer-api-club",
            admin=admin,
        )
        ClubAdminScope.objects.create(
            user=admin,
            club=club,
            role=role,
        )
        return club

    def _payload(self, **overrides):
        payload = {
            "workspace": self.workspace.id,
            "source_registration": self.registration.id,
            "destination_club": self.destination_club.id,
            "destination_team": self.destination_team.id,
            "effective_on": "2026-08-01",
            "transfer_type": "PERMANENT",
            "documents": ["maintained-document-reference"],
            "fee_status": "PAID",
        }
        payload.update(overrides)
        return payload

    def _draft(self, **overrides):
        values = {
            "actor": self.destination_actor,
            "workspace": self.workspace,
            "source_registration": self.registration,
            "destination_club": self.destination_club,
            "destination_team": self.destination_team,
            "effective_on": date(2026, 8, 1),
            "transfer_type": "PERMANENT",
            "documents": ["maintained-document-reference"],
            "fee_status": "PAID",
        }
        values.update(overrides)
        return create_player_transfer_draft(**values)

    def _submitted(self):
        transfer = self._draft()
        return submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )

    @staticmethod
    def _detail_url(transfer):
        return f"/api/teams/player-transfer-submissions/{transfer.id}/"

    @staticmethod
    def _action_url(transfer, action):
        return f"/api/teams/player-transfer-submissions/{transfer.id}/{action}/"

    def test_destination_chairman_creates_draft(self):
        response = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        transfer = UnionPlayerTransfer.objects.get()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.DRAFT)
        self.assertEqual(transfer.initiated_by, self.destination_actor)
        self.assertEqual(response.data["source_club"], self.source_club.id)

    def test_club_admin_without_transfer_permission_receives_403(self):
        self.client.force_authenticate(self.no_permission_actor)
        response = self.client.post(
            self.list_url,
            self._payload(
                destination_club=self.no_permission_club.id,
                destination_team=self.no_permission_team.id,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(UnionPlayerTransfer.objects.exists())

    def test_unrelated_club_user_cannot_create_transfer(self):
        self.client.force_authenticate(self.unrelated_actor)
        response = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destination_club", response.data)

    def test_server_controlled_draft_fields_are_rejected(self):
        for field in (
            "player",
            "status",
            "reviewed_by",
            "activation_plan",
            "return_plan",
            "completed_at",
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url,
                    self._payload(**{field: "controlled"}),
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_invalid_workspace_relationship_returns_400(self):
        response = self.client.post(
            self.list_url,
            self._payload(workspace=self.outside_workspace.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source_club", response.data)

    def test_invalid_destination_team_returns_400(self):
        response = self.client.post(
            self.list_url,
            self._payload(destination_team=self.unrelated_team.id),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destination_team", response.data)

    def test_valid_loan_payload_is_private_and_creates_draft(self):
        response = self.client.post(
            self.list_url,
            self._payload(transfer_type="LOAN", loan_end_on="2026-10-01"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["transfer_type"], "LOAN")
        self.assertNotIn("activation_plan", response.data)
        self.assertNotIn("return_plan", response.data)

    def test_destination_sees_draft_but_source_and_player_do_not(self):
        transfer = self._draft()
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 1)
        for actor in (self.source_actor, self.player_user):
            with self.subTest(actor=actor.email):
                self.client.force_authenticate(actor)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data, {"count": 0, "results": []})
        self.assertTrue(UnionPlayerTransfer.objects.filter(pk=transfer.id).exists())

    def test_submitted_transfer_is_visible_to_source_player_not_unrelated(self):
        transfer = self._submitted()
        for actor, expected_count in (
            (self.source_actor, 1),
            (self.player_user, 1),
            (self.unrelated_actor, 0),
        ):
            with self.subTest(actor=actor.email):
                self.client.force_authenticate(actor)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], expected_count)
                detail_response = self.client.get(self._detail_url(transfer))
                self.assertEqual(
                    detail_response.status_code,
                    (
                        status.HTTP_200_OK
                        if expected_count
                        else status.HTTP_404_NOT_FOUND
                    ),
                )
        self.assertIsNotNone(transfer.submitted_at)

    def test_status_and_club_filters_work(self):
        transfer = self._draft()
        response = self.client.get(
            self.list_url,
            {
                "status": [UnionPlayerTransfer.Status.DRAFT],
                "destination_club": self.destination_club.id,
            },
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], transfer.id)
        response = self.client.get(
            self.list_url,
            {"source_club": self.destination_club.id},
        )
        self.assertEqual(response.data["count"], 0)

    def test_search_and_safe_ordering_work(self):
        transfer = self._draft()
        response = self.client.get(
            self.list_url,
            {"search": "Martha", "ordering": "player_name"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], transfer.id)
        response = self.client.get(self.list_url, {"ordering": "status;drop"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_destination_can_retrieve_and_update_draft(self):
        transfer = self._draft()
        response = self.client.get(self._detail_url(transfer))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(
            self._detail_url(transfer),
            {"fee_status": "SETTLED", "destination_team": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.assertEqual(transfer.fee_status, "SETTLED")
        self.assertIsNone(transfer.destination_team)

    def test_source_and_player_receive_404_for_unsubmitted_detail(self):
        transfer = self._draft()
        for actor in (self.source_actor, self.player_user):
            with self.subTest(actor=actor.email):
                self.client.force_authenticate(actor)
                response = self.client.get(self._detail_url(transfer))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_source_and_player_cannot_patch_destination_terms(self):
        transfer = self._submitted()
        for actor in (self.source_actor, self.player_user):
            with self.subTest(actor=actor.email):
                self.client.force_authenticate(actor)
                response = self.client.patch(
                    self._detail_url(transfer),
                    {"fee_status": "SETTLED"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_controlled_update_fields_are_rejected(self):
        transfer = self._draft()
        for field in ("status", "workspace", "destination_club", "decision_reason"):
            with self.subTest(field=field):
                response = self.client.patch(
                    self._detail_url(transfer),
                    {field: "controlled"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_detail_put_delete_and_post_return_405(self):
        transfer = self._draft()
        for method in ("put", "delete", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._detail_url(transfer),
                    {},
                    format="json",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )

    def test_destination_can_submit(self):
        transfer = self._draft()
        response = self.client.post(self._action_url(transfer, "submit"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.assertEqual(
            transfer.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        self.assertEqual(transfer.submission_revision, 1)

    def test_blocking_submission_preserves_structured_validation(self):
        transfer = self._draft(documents=[])
        response = self.client.post(self._action_url(transfer, "submit"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            ["Player transfer contains blocking validation errors."],
        )
        self.assertEqual(response.data["automatic_validation"]["version"], 1)
        self.assertTrue(
            response.data["automatic_validation"]["blocking_errors"],
        )

    def test_destination_can_resubmit_changes_requested_transfer(self):
        transfer = self._draft()
        transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
        transfer.submitted_at = timezone.now()
        transfer.save(update_fields=["status", "submitted_at"])
        response = self.client.post(self._action_url(transfer, "resubmit"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.assertEqual(transfer.submission_revision, 1)
        self.assertIsNotNone(transfer.last_resubmitted_at)

    def test_destination_can_cancel_before_review_and_reason_is_required(self):
        transfer = self._draft()
        response = self.client.post(
            self._action_url(transfer, "cancel"),
            {"reason": "Destination Club withdrew."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, UnionPlayerTransfer.Status.CANCELLED)
        self.assertTrue(UnionPlayerTransfer.objects.filter(pk=transfer.id).exists())
        other = self._draft()
        response = self.client.post(
            self._action_url(other, "cancel"),
            {"reason": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_source_club_can_acknowledge(self):
        transfer = self._submitted()
        self.client.force_authenticate(self.source_actor)
        response = self.client.post(
            self._action_url(transfer, "source-response"),
            {
                "response_status": "ACKNOWLEDGED",
                "response": "The source Club acknowledges.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_club_response_status"], "ACKNOWLEDGED")

    def test_source_club_can_object_but_blank_objection_is_rejected(self):
        transfer = self._submitted()
        self.client.force_authenticate(self.source_actor)
        response = self.client.post(
            self._action_url(transfer, "source-response"),
            {"response_status": "OBJECTED", "response": "Date is disputed."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transfer.refresh_from_db()
        self.assertEqual(
            transfer.status,
            UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        )
        transfer.status = UnionPlayerTransfer.Status.CANCELLED
        transfer.save(update_fields=["status"])
        other = self._draft()
        submit_player_transfer(
            transfer_id=other.id,
            actor=self.destination_actor,
        )
        response = self.client.post(
            self._action_url(other, "source-response"),
            {"response_status": "OBJECTED", "response": "  "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("response", response.data)

    def test_destination_club_cannot_respond_for_source(self):
        transfer = self._submitted()
        response = self.client.post(
            self._action_url(transfer, "source-response"),
            {"response_status": "ACKNOWLEDGED", "response": "Invalid actor."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_linked_player_can_consent(self):
        transfer = self._submitted()
        self.client.force_authenticate(self.player_user)
        response = self.client.post(
            self._action_url(transfer, "consent"),
            {"consent_method": "Authenticated League OS account confirmation"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["player_consent_status"], "CONSENTED")

    def test_linked_player_can_decline_without_deletion(self):
        transfer = self._submitted()
        self.client.force_authenticate(self.player_user)
        response = self.client.post(
            self._action_url(transfer, "decline"),
            {"reason": "I do not agree."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UnionPlayerTransfer.Status.CANCELLED)
        self.assertTrue(UnionPlayerTransfer.objects.filter(pk=transfer.id).exists())

    def test_club_and_unrelated_users_cannot_impersonate_player(self):
        transfer = self._submitted()
        for actor in (self.destination_actor, self.unrelated_actor):
            with self.subTest(actor=actor.email):
                self.client.force_authenticate(actor)
                response = self.client.post(
                    self._action_url(transfer, "consent"),
                    {"consent_method": "Impersonated"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_consent_rejects_offline_evidence_fields(self):
        transfer = self._submitted()
        self.client.force_authenticate(self.player_user)
        for field in ("membership", "evidence_reference"):
            with self.subTest(field=field):
                response = self.client.post(
                    self._action_url(transfer, "consent"),
                    {
                        "consent_method": "Direct",
                        field: "not-permitted",
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_list_and_detail_privacy_and_no_direct_approval_route(self):
        transfer = self._draft()
        list_response = self.client.get(self.list_url)
        list_item = list_response.data["results"][0]
        for field in (
            "documents",
            "automatic_validation",
            "decision_reason",
            "activation_plan",
            "return_plan",
        ):
            self.assertNotIn(field, list_item)
        detail_response = self.client.get(self._detail_url(transfer))
        for field in (
            "activation_plan",
            "return_plan",
            "identity_reference",
            "date_of_birth",
        ):
            self.assertNotIn(field, detail_response.data)
        response = self.client.post(self._action_url(transfer, "approve"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
