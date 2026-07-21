from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Club, ClubAdminScope, User
from teams.models import Team

from .models import (
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
    UnionWorkspaceMembership,
)
from .union_player_transfer_return_services import return_loaned_player_to_source
from .union_player_transfer_services import (
    create_player_transfer_draft,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    submit_player_transfer,
)


class UnionPlayerTransferAPITests(TestCase):
    list_url = "/api/dashboards/union-admin/player-transfers/"

    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        self.union = Union.objects.create(
            name="Transfer API Union",
            slug="transfer-api-union",
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
            name=str(self.today.year),
            slug=f"transfer-api-{self.today.year}",
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=365),
        )
        self.destination_actor = self._user("destination", User.Role.CLUB_ADMIN)
        self.source_actor = self._user("source", User.Role.CLUB_ADMIN)
        self.reviewer = self._user("reviewer", User.Role.FAN)
        self.viewer = self._user("viewer", User.Role.FAN)
        self.no_view = self._user("no-view", User.Role.FAN)
        self.source_club = self._club("Source", self.source_actor)
        self.destination_club = self._club(
            "Destination",
            self.destination_actor,
        )
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Transfer API Source Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Transfer API Destination Team",
        )
        for club in (self.source_club, self.destination_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.identity, self.edition = self._competition("primary")
        self.membership = self._membership(
            self.reviewer,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        self.viewer_membership = self._membership(
            self.viewer,
            UnionWorkspaceMembership.Role.VIEWER,
        )
        self.no_view_membership = self._membership(
            self.no_view,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        self.player_user, self.player, self.registration, self.eligibility = (
            self._player_case("primary")
        )

    def _user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}-{User.objects.count()}@leagueos.test",
            password="StrongPass123!",
            role=role,
        )

    def _club(self, prefix, admin):
        club = Club.objects.create(
            name=f"{prefix} Transfer API Club",
            slug=f"{prefix.lower()}-transfer-api-club",
            admin=admin,
        )
        ClubAdminScope.objects.create(
            user=admin,
            club=club,
            role=ClubAdminScope.Role.CHAIRMAN,
        )
        return club

    def _membership(
        self,
        user,
        role,
        *,
        workspace=None,
        is_active=True,
        scope_restrictions=None,
    ):
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace or self.workspace,
            role=role,
            is_active=is_active,
            scope_restrictions=scope_restrictions or {},
        )

    def _competition(self, suffix):
        identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name=f"Transfer API Cup {suffix}",
            slug=f"transfer-api-cup-{suffix}",
        )
        competition = Competition.objects.create(
            league=self.league,
            name=f"Transfer API Competition {suffix}",
            slug=f"transfer-api-competition-{suffix}",
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

    def _player_case(self, suffix):
        player_user = self._user(f"player-{suffix}", User.Role.FAN)
        player = UnionPlayer.objects.create(
            union=self.union,
            user=player_user,
            union_player_number=f"TAPI-P{UnionPlayer.objects.count() + 1:06d}",
            first_name="Transfer",
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
                    "code": "API_WARNING",
                    "field": "player",
                    "message": "Maintained warning.",
                    "severity": "WARNING",
                    "private_extra": "PRIVATE-WARNING-EVIDENCE",
                }
            ],
        )
        return player_user, player, registration, eligibility

    def _submitted(
        self,
        *,
        case=None,
        transfer_type="PERMANENT",
        effective_on=None,
    ):
        player_user, player, registration, eligibility = case or (
            self.player_user,
            self.player,
            self.registration,
            self.eligibility,
        )
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
            documents=["PRIVATE-TRANSFER-DOCUMENT"],
            fee_status="PAID",
        )
        transfer = submit_player_transfer(
            transfer_id=transfer.id,
            actor=self.destination_actor,
        )
        return transfer, player_user, player, registration, eligibility

    def _under_review(
        self,
        *,
        case=None,
        transfer_type="PERMANENT",
        effective_on=None,
    ):
        transfer, player_user, player, registration, eligibility = self._submitted(
            case=case,
            transfer_type=transfer_type,
            effective_on=effective_on,
        )
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=(UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED),
            response="PRIVATE-SOURCE-RESPONSE",
        )
        transfer = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=player_user,
            consent_method="PLAYER_PORTAL",
        )
        return transfer, player, registration, eligibility

    def _authenticate(self, user=None):
        self.client.force_authenticate(user or self.reviewer)

    def _detail_url(self, transfer):
        return f"{self.list_url}{transfer.id}/"

    def _action_url(self, transfer, action):
        return f"{self._detail_url(transfer)}{action}/"

    def _post_action(self, transfer, action, **values):
        payload = {
            "workspace": self.workspace.id,
            "reason": "Maintained Union transfer decision.",
        }
        payload.update(values)
        return self.client.post(
            self._action_url(transfer, action),
            payload,
            format="json",
        )

    def test_workspace_is_explicit_and_inaccessible_workspace_is_forbidden(self):
        self._authenticate()
        missing = self.client.get(self.list_url)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        other_union = Union.objects.create(name="Other API Union", slug="other-api")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other API Workspace",
            slug="other-api-workspace",
            acronym="OAW",
            sport="Football",
        )
        inaccessible = self.client.get(
            self.list_url,
            {"workspace": other_workspace.id},
        )
        self.assertEqual(inaccessible.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_view_member_can_list_and_view(self):
        transfer = self._submitted()[0]
        self._authenticate(self.viewer)
        listed = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id},
        )
        detail = self.client.get(
            self._detail_url(transfer),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_missing_view_permission_and_inactive_membership_are_forbidden(self):
        self._authenticate(self.no_view)
        no_permission = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id},
        )
        self.assertEqual(no_permission.status_code, status.HTTP_403_FORBIDDEN)

        self.viewer_membership.is_active = False
        self.viewer_membership.save(update_fields=["is_active"])
        self._authenticate(self.viewer)
        inactive = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id},
        )
        self.assertEqual(inactive.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_only_member_cannot_act_but_approver_can(self):
        transfer = self._under_review()[0]
        self._authenticate(self.viewer)
        denied = self._post_action(transfer, "request-changes")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self._authenticate()
        allowed = self._post_action(transfer, "request-changes")
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data["status"], "CHANGES_REQUESTED")

    def test_drafts_are_excluded_even_when_requested(self):
        draft = create_player_transfer_draft(
            actor=self.destination_actor,
            workspace=self.workspace,
            source_registration=self.registration,
            destination_club=self.destination_club,
            destination_team=self.destination_team,
            effective_on=self.today,
            transfer_type="PERMANENT",
            documents=["PRIVATE"],
            fee_status="PAID",
        )
        self._authenticate()
        listed = self.client.get(
            f"{self.list_url}?workspace={self.workspace.id}&status=DRAFT"
        )
        detail = self.client.get(
            self._detail_url(draft),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(listed.data, {"count": 0, "results": []})
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_prerequisite_and_terminal_transfers_are_visible(self):
        transfer = self._submitted()[0]
        transfer.status = UnionPlayerTransfer.Status.REJECTED
        transfer.save(update_fields=["status"])
        self._authenticate()
        response = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "REJECTED")

    def test_other_workspace_transfer_is_excluded_and_detail_is_not_found(self):
        transfer = self._submitted()[0]
        other_union = Union.objects.create(
            name="Scoped Other Union",
            slug="scoped-other-union",
        )
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Scoped Other Workspace",
            slug="scoped-other-workspace",
            acronym="SOW",
            sport="Football",
        )
        UnionPlayerTransfer.objects.filter(pk=transfer.id).update(
            workspace=other_workspace
        )
        self._authenticate()
        listed = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id},
        )
        detail = self.client.get(
            self._detail_url(transfer),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(listed.data["count"], 0)
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_both_source_and_destination_club_scopes_are_required(self):
        transfer = self._submitted()[0]
        self._authenticate()
        for club_ids in (
            [self.source_club.id],
            [self.destination_club.id],
        ):
            with self.subTest(club_ids=club_ids):
                self.membership.scope_restrictions = {"club_ids": club_ids}
                self.membership.save(update_fields=["scope_restrictions"])
                listed = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id},
                )
                detail = self.client.get(
                    self._detail_url(transfer),
                    {"workspace": self.workspace.id},
                )
                action = self._post_action(transfer, "record-offline-decline")
                self.assertEqual(listed.data["count"], 0)
                self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(action.status_code, status.HTTP_404_NOT_FOUND)

    def test_source_destination_and_return_eligibility_scopes_are_enforced(self):
        transfer = self._submitted()[0]
        other_identity, other_edition = self._competition("outside")
        UnionPlayerCompetitionEligibility.objects.create(
            workspace=self.workspace,
            player=self.player,
            registration=self.registration,
            source_transfer=transfer,
            club=self.destination_club,
            team=self.destination_team,
            competition_identity=other_identity,
            competition_edition=other_edition,
            season=self.season,
        )
        self._authenticate()
        base = {
            "club_ids": [self.source_club.id, self.destination_club.id],
        }
        restrictions = (
            {
                **base,
                "competition_identity_ids": [self.identity.id],
            },
            {
                **base,
                "competition_identity_ids": [
                    self.identity.id,
                    other_identity.id,
                ],
                "competition_edition_ids": [self.edition.id],
            },
        )
        for scope_restrictions in restrictions:
            with self.subTest(scope_restrictions=scope_restrictions):
                self.membership.scope_restrictions = scope_restrictions
                self.membership.save(update_fields=["scope_restrictions"])
                response = self.client.get(
                    self._detail_url(transfer),
                    {"workspace": self.workspace.id},
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_club_player_and_registration_filters_work(self):
        transfer = self._submitted()[0]
        self._authenticate()
        filters = {
            "status": transfer.status,
            "player": self.player.id,
            "source_registration": self.registration.id,
            "source_club": self.source_club.id,
            "destination_club": self.destination_club.id,
            "destination_team": self.destination_team.id,
            "transfer_type": transfer.transfer_type,
            "source_response_status": transfer.source_club_response_status,
            "player_consent_status": transfer.player_consent_status,
            "initiated_by": self.destination_actor.id,
        }
        for parameter, value in filters.items():
            with self.subTest(parameter=parameter):
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id, parameter: value},
                )
                self.assertEqual(response.data["count"], 1)

    def test_repeated_status_date_filters_and_search_work(self):
        transfer = self._submitted()[0]
        self._authenticate()
        repeated = self.client.get(
            f"{self.list_url}?workspace={self.workspace.id}"
            f"&status={transfer.status}&status=REJECTED"
        )
        self.assertEqual(repeated.data["count"], 1)
        for filters in (
            {"effective_from": self.today.isoformat()},
            {"effective_to": self.today.isoformat()},
            {"submitted_from": self.today.isoformat()},
            {"created_to": self.today.isoformat()},
        ):
            with self.subTest(filters=filters):
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id, **filters},
                )
                self.assertEqual(response.data["count"], 1)
        for search in (
            self.player.union_player_number,
            self.player.first_name,
            self.source_club.name,
            self.destination_club.name,
        ):
            with self.subTest(search=search):
                response = self.client.get(
                    self.list_url,
                    {"workspace": self.workspace.id, "search": search},
                )
                self.assertEqual(response.data["count"], 1)

    def test_safe_ordering_and_arbitrary_ordering_fallback(self):
        self._submitted()
        second_case = self._player_case("ordering")
        second = self._submitted(case=second_case)[0]
        self._authenticate()
        safe = self.client.get(
            self.list_url,
            {"workspace": self.workspace.id, "ordering": "player_name"},
        )
        arbitrary = self.client.get(
            self.list_url,
            {
                "workspace": self.workspace.id,
                "ordering": "status; DROP TABLE dashboards",
            },
        )
        self.assertEqual(safe.status_code, status.HTTP_200_OK)
        self.assertEqual(arbitrary.status_code, status.HTTP_200_OK)
        self.assertEqual(arbitrary.data["results"][0]["id"], second.id)

    def test_detail_contract_is_read_only_and_excludes_private_fields(self):
        transfer = self._submitted()[0]
        transfer.activation_plan = {"private": "PRIVATE-ACTIVATION"}
        transfer.return_plan = {"private": "PRIVATE-RETURN"}
        transfer.save(update_fields=["activation_plan", "return_plan"])
        self._authenticate()
        response = self.client.get(
            self._detail_url(transfer),
            {"workspace": self.workspace.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["documents"], ["PRIVATE-TRANSFER-DOCUMENT"])
        for field in (
            "activation_plan",
            "return_plan",
            "identity_reference",
            "date_of_birth",
            "evidence_reference",
            "audit_metadata",
            "notifications",
        ):
            self.assertNotIn(field, response.data)
        for method in ("post", "patch", "put", "delete"):
            with self.subTest(method=method):
                denied = getattr(self.client, method)(
                    self._detail_url(transfer),
                    {"workspace": self.workspace.id},
                    format="json",
                )
                self.assertEqual(
                    denied.status_code,
                    status.HTTP_405_METHOD_NOT_ALLOWED,
                )

    def test_offline_consent_requires_complete_explicit_contract(self):
        transfer = self._submitted()[0]
        self._authenticate()
        for payload in (
            {"workspace": self.workspace.id, "consent_method": "PAPER"},
            {
                "workspace": self.workspace.id,
                "evidence_reference": "OPAQUE-EVIDENCE",
            },
            {
                "workspace": self.workspace.id,
                "consent_method": "PAPER",
                "evidence_reference": "OPAQUE-EVIDENCE",
                "status": "CONSENTED",
            },
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    self._action_url(transfer, "record-offline-consent"),
                    payload,
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authorised_offline_consent_advances_prerequisites_without_evidence_echo(
        self,
    ):
        transfer = self._submitted()[0]
        record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=self.source_actor,
            response_status=(UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED),
            response="Acknowledged.",
        )
        self._authenticate()
        response = self.client.post(
            self._action_url(transfer, "record-offline-consent"),
            {
                "workspace": self.workspace.id,
                "consent_method": "SIGNED_FORM",
                "evidence_reference": "PRIVATE-OFFLINE-CONSENT-EVIDENCE",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["player_consent_status"], "CONSENTED")
        self.assertEqual(response.data["status"], "UNDER_UNION_REVIEW")
        self.assertNotIn("evidence_reference", str(response.data))

    def test_viewer_cannot_record_offline_consent(self):
        transfer = self._submitted()[0]
        self._authenticate(self.viewer)
        response = self.client.post(
            self._action_url(transfer, "record-offline-consent"),
            {
                "workspace": self.workspace.id,
                "consent_method": "SIGNED_FORM",
                "evidence_reference": "OPAQUE",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_offline_decline_cancels_without_deleting_or_echoing_evidence(self):
        transfer = self._submitted()[0]
        self._authenticate()
        response = self.client.post(
            self._action_url(transfer, "record-offline-decline"),
            {
                "workspace": self.workspace.id,
                "reason": "The player declined the proposed movement.",
                "evidence_reference": "PRIVATE-OFFLINE-DECLINE-EVIDENCE",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["player_consent_status"], "DECLINED")
        self.assertEqual(response.data["status"], "CANCELLED")
        self.assertTrue(UnionPlayerTransfer.objects.filter(pk=transfer.id).exists())
        self.assertNotIn("evidence_reference", str(response.data))

    def test_request_changes_requires_reason_and_independent_reviewer(self):
        transfer = self._under_review()[0]
        self._authenticate()
        blank = self._post_action(transfer, "request-changes", reason=" ")
        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)

        transfer.initiated_by = self.reviewer
        transfer.save(update_fields=["initiated_by"])
        self_review = self._post_action(transfer, "request-changes")
        self.assertEqual(self_review.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reviewer", self_review.data)

    def test_rejection_returns_fresh_validation_and_preserves_registration(self):
        transfer, _, registration, _ = self._under_review()
        self._authenticate()
        response = self._post_action(transfer, "reject")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["transfer"]["status"], "REJECTED")
        self.assertEqual(response.data["automatic_validation"]["version"], 1)
        self.assertEqual(
            response.data["automatic_validation"]["blocking_errors"],
            [],
        )
        registration.refresh_from_db()
        self.assertEqual(registration.status, UnionPlayerRegistration.Status.ACTIVE)

    def test_decisions_reject_server_controlled_fields(self):
        transfer = self._under_review()[0]
        self._authenticate()
        for field in (
            "status",
            "reviewed_by",
            "effective_on",
            "destination_registration",
            "activation_plan",
            "return_plan",
        ):
            with self.subTest(field=field):
                response = self._post_action(
                    transfer,
                    "approve",
                    **{field: "not-permitted"},
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_immediate_permanent_and_free_approval_return_successors(self):
        self._authenticate()
        for index, transfer_type in enumerate(("PERMANENT", "FREE_TRANSFER")):
            with self.subTest(transfer_type=transfer_type):
                case = None if index == 0 else self._player_case("immediate-free")
                transfer, _, _, _ = self._under_review(
                    case=case,
                    transfer_type=transfer_type,
                )
                response = self._post_action(transfer, "approve")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["transfer"]["status"], "COMPLETED")
                self.assertIsNotNone(response.data["destination_registration"])
                self.assertFalse(response.data["activation_scheduled"])
                self.assertFalse(response.data["idempotent_replay"])
                self.assertNotIn("activation_plan", response.data["transfer"])
                self.assertNotIn("return_plan", response.data["transfer"])

    def test_immediate_loan_approval_returns_active_loan_and_pending_eligibility(self):
        transfer, _, _, _ = self._under_review(transfer_type="LOAN")
        self._authenticate()
        response = self._post_action(transfer, "approve")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["transfer"]["status"], "LOAN_ACTIVE")
        self.assertEqual(
            response.data["destination_registration"]["registration_type"],
            "LOAN",
        )
        self.assertEqual(len(response.data["destination_eligibilities"]), 1)
        self.assertEqual(
            response.data["destination_eligibilities"][0]["status"],
            "PENDING",
        )
        self.assertFalse(response.data["activation_scheduled"])

    def test_future_permanent_free_and_loan_approval_is_scheduled(self):
        self._authenticate()
        for index, transfer_type in enumerate(("PERMANENT", "FREE_TRANSFER", "LOAN")):
            with self.subTest(transfer_type=transfer_type):
                case = None if index == 0 else self._player_case(f"scheduled-{index}")
                transfer, _, _, _ = self._under_review(
                    case=case,
                    transfer_type=transfer_type,
                    effective_on=self.today + timedelta(days=2),
                )
                response = self._post_action(transfer, "approve")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["transfer"]["status"], "APPROVED")
                self.assertTrue(response.data["activation_scheduled"])
                self.assertIsNone(response.data["destination_registration"])
                self.assertEqual(response.data["destination_eligibilities"], [])

    def test_blocking_approval_preserves_automatic_validation(self):
        transfer, _, registration, _ = self._under_review()
        registration.status = UnionPlayerRegistration.Status.SUSPENDED
        registration.save(update_fields=["status"])
        self._authenticate()
        response = self._post_action(transfer, "approve")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("automatic_validation", response.data)
        self.assertTrue(response.data["automatic_validation"]["blocking_errors"])

    def test_scheduled_and_completed_approval_replays_are_idempotent(self):
        self._authenticate()
        scheduled = self._under_review(effective_on=self.today + timedelta(days=2))[0]
        first_scheduled = self._post_action(scheduled, "approve")
        scheduled_replay = self._post_action(scheduled, "approve")
        self.assertTrue(first_scheduled.data["activation_scheduled"])
        self.assertTrue(scheduled_replay.data["activation_scheduled"])
        self.assertTrue(scheduled_replay.data["idempotent_replay"])

        completed = self._under_review(case=self._player_case("replay"))[0]
        first = self._post_action(completed, "approve")
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        replay = self._post_action(completed, "approve")
        self.assertTrue(replay.data["idempotent_replay"])
        self.assertEqual(
            replay.data["destination_registration"]["id"],
            first.data["destination_registration"]["id"],
        )
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )

    def test_active_and_completed_loan_replays_are_normalised(self):
        transfer = self._under_review(transfer_type="LOAN")[0]
        self._authenticate()
        first = self._post_action(transfer, "approve")
        active_replay = self._post_action(transfer, "approve")
        self.assertTrue(active_replay.data["idempotent_replay"])
        self.assertEqual(
            active_replay.data["destination_registration"]["id"],
            first.data["destination_registration"]["id"],
        )

        returned = return_loaned_player_to_source(
            transfer_id=transfer.id,
            as_of=transfer.loan_end_on + timedelta(days=1),
        )
        registration_count = UnionPlayerRegistration.objects.count()
        eligibility_count = UnionPlayerCompetitionEligibility.objects.count()
        completed_replay = self._post_action(transfer, "approve")
        self.assertTrue(completed_replay.data["idempotent_replay"])
        self.assertEqual(
            completed_replay.data["return_registration"]["id"],
            returned["return_registration"].id,
        )
        self.assertEqual(len(completed_replay.data["return_eligibilities"]), 1)
        self.assertEqual(completed_replay.data["destination_eligibilities"], [])
        self.assertEqual(UnionPlayerRegistration.objects.count(), registration_count)
        self.assertEqual(
            UnionPlayerCompetitionEligibility.objects.count(),
            eligibility_count,
        )

    def test_union_create_update_and_direct_movement_routes_are_unavailable(self):
        transfer = self._submitted()[0]
        self._authenticate()
        create = self.client.post(
            self.list_url,
            {"workspace": self.workspace.id},
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        for action in (
            "activate",
            "process-activation",
            "return-loan",
            "process-return",
            "start-review",
            "create-registration",
            "create-eligibility",
        ):
            with self.subTest(action=action):
                response = self.client.post(
                    self._action_url(transfer, action),
                    {"workspace": self.workspace.id},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
