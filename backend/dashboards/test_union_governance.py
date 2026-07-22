from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import (
    UNION_WORKSPACE_ROLE_PERMISSIONS,
    UnionApproval,
    UnionAuditEvent,
    ClubAffiliation,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from dashboards.union_governance import request_union_approval, review_union_approval


class UnionGovernanceTests(APITestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Governance Union", slug="governance-union"
        )
        self.other_union = Union.objects.create(
            name="Other Governance Union",
            slug="other-governance-union",
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Governance Workspace",
            slug="governance-workspace",
            acronym="GW",
            sport="Football",
        )
        self.other_workspace = UnionWorkspace.objects.create(
            related_union=self.other_union,
            name="Other Governance Workspace",
            slug="other-governance-workspace",
            acronym="OGW",
            sport="Football",
        )
        self.requester = self._user("requester@leagueos.test")
        self.reviewer = self._user("reviewer@leagueos.test")
        self.viewer = self._user("viewer@leagueos.test")
        self.other_owner = self._user("other-owner@leagueos.test")
        self._membership(self.requester, self.workspace, "OWNER")
        self._membership(self.reviewer, self.workspace, "OWNER")
        self._membership(self.viewer, self.workspace, "VIEWER")
        self._membership(self.other_owner, self.other_workspace, "OWNER")

    def _user(self, email):
        return User.objects.create_user(
            email=email,
            password="StrongPass123!",
            first_name="Union",
            last_name="User",
            is_email_verified=True,
        )

    def _membership(self, user, workspace, role):
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace,
            role=role,
        )

    def test_role_templates_expose_the_new_granular_permissions(self):
        owner_permissions = UNION_WORKSPACE_ROLE_PERMISSIONS["OWNER"]
        self.assertTrue(
            {
                "union.competitions.publish",
                "union.transfers.approve",
                "union.statistics.manage",
                "union.finance.manage",
                "union.audit.view",
                "union.approvals.manage",
            }.issubset(owner_permissions)
        )
        self.assertIn(
            "union.sponsors.manage",
            UNION_WORKSPACE_ROLE_PERMISSIONS["SPONSORSHIP_OFFICER"],
        )
        self.assertIn(
            "union.teams.manage",
            UNION_WORKSPACE_ROLE_PERMISSIONS["NATIONAL_TEAM_MANAGER"],
        )

    def test_reviewer_cannot_approve_own_request_and_a_decision_is_audited(self):
        approval = request_union_approval(
            workspace=self.workspace,
            subject_type="promotion_proposal",
            subject_id=42,
            action="promotion.override",
            requested_by=self.requester,
            reason="Licensing exception",
        )

        with self.assertRaises(ValidationError):
            review_union_approval(
                approval_id=approval.id,
                reviewer=self.requester,
                approved=True,
                decision_reason="Approved",
            )

        reviewed = review_union_approval(
            approval_id=approval.id,
            reviewer=self.reviewer,
            approved=True,
            decision_reason="Documentation verified",
        )
        self.assertEqual(reviewed.status, UnionApproval.Status.APPROVED)
        self.assertEqual(reviewed.reviewed_by, self.reviewer)
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                workspace=self.workspace,
                action="approval.approved",
                target_id=approval.id,
            ).exists()
        )

    def test_audit_events_are_append_only(self):
        event = UnionAuditEvent.objects.create(
            workspace=self.workspace,
            actor=self.requester,
            action="test.created",
        )
        event.action = "test.changed"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_approval_list_is_workspace_isolated_and_viewers_are_denied(self):
        local = request_union_approval(
            workspace=self.workspace,
            subject_type="competition_edition",
            subject_id=7,
            action="competition.publish",
            requested_by=self.requester,
        )
        request_union_approval(
            workspace=self.other_workspace,
            subject_type="competition_edition",
            subject_id=8,
            action="competition.publish",
            requested_by=self.other_owner,
        )

        self.client.force_authenticate(self.reviewer)
        response = self.client.get(
            "/api/dashboards/union-admin/approvals/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], local.id)

        self.client.force_authenticate(self.viewer)
        denied_response = self.client.get(
            "/api/dashboards/union-admin/approvals/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_and_document_creation_create_workspace_audit_events(self):
        club = Club.objects.create(name="Governance Club", slug="governance-club")
        affiliation = ClubAffiliation.objects.create(
            workspace=self.workspace,
            club=club,
        )
        self.client.force_authenticate(self.requester)
        comment_response = self.client.post(
            "/api/dashboards/union-admin/review-comments/",
            {
                "workspace": self.workspace.slug,
                "subject_type": "club_affiliation",
                "subject_id": affiliation.id,
                "body": "Identity document needs a clearer scan.",
            },
            format="json",
        )
        self.assertEqual(comment_response.status_code, status.HTTP_201_CREATED)
        document_response = self.client.post(
            "/api/dashboards/union-admin/documents/",
            {
                "workspace": self.workspace.slug,
                "subject_type": "club_affiliation",
                "subject_id": affiliation.id,
                "document_type": "IDENTITY",
                "title": "Player identity card",
                "file_url": "https://files.example.test/player-id.pdf",
            },
            format="json",
        )
        self.assertEqual(document_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            UnionAuditEvent.objects.filter(workspace=self.workspace).count(),
            2,
        )
