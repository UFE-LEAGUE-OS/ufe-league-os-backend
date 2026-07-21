from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dashboards.management.commands.seed_union_workflow_coverage import DEMO_KEY
from dashboards.models import (
    ClubAffiliation,
    FixtureOfficialAssignment,
    NationalTeam,
    NationalTeamMember,
    UnionApproval,
    UnionAuditEvent,
    UnionDocumentReference,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionRegistrationApplication,
    UnionReviewComment,
    UnionWorkspace,
)


class SeedUnionWorkflowCoverageTests(TestCase):
    def setUp(self):
        call_command("seed_union_workspaces", stdout=StringIO())
        call_command(
            "seed_union_test_users",
            password="StrongPass123!",
            stdout=StringIO(),
        )
        call_command("seed_union_operations_demo_data", stdout=StringIO())

    def run_seed(self):
        output = StringIO()
        call_command("seed_union_workflow_coverage", stdout=output)
        return output.getvalue()

    def coverage_workspace(self):
        return UnionWorkspace.objects.get(acronym="URU")

    def test_seed_covers_union_workflow_statuses(self):
        output = self.run_seed()
        workspace = self.coverage_workspace()
        players = UnionPlayer.objects.filter(
            union=workspace.related_union,
            metadata__demo_key=DEMO_KEY,
        )

        self.assertTrue(
            set(UnionPlayer.Status.values).issubset(
                set(players.values_list("status", flat=True))
            )
        )
        self.assertTrue(
            set(UnionPlayerRegistration.Status.values).issubset(
                set(
                    UnionPlayerRegistration.objects.filter(
                        workspace=workspace,
                        player__metadata__demo_key=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(UnionPlayerCompetitionEligibility.Status.values).issubset(
                set(
                    UnionPlayerCompetitionEligibility.objects.filter(
                        workspace=workspace,
                        player__metadata__demo_key=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(UnionPlayerTransfer.Status.values).issubset(
                set(
                    UnionPlayerTransfer.objects.filter(
                        workspace=workspace,
                        player__metadata__demo_key=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(ClubAffiliation.Status.values).issubset(
                set(
                    ClubAffiliation.objects.filter(
                        workspace=workspace,
                        compliance_notes__contains=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(UnionRegistrationApplication.Status.values).issubset(
                set(
                    UnionRegistrationApplication.objects.filter(
                        workspace=workspace,
                        metadata__demo_key=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(UnionApproval.Status.values).issubset(
                set(
                    UnionApproval.objects.filter(
                        workspace=workspace,
                        metadata__demo_key=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(NationalTeam.Status.values).issubset(
                set(
                    NationalTeam.objects.filter(
                        workspace=workspace,
                        notes__contains=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(NationalTeamMember.Status.values).issubset(
                set(
                    NationalTeamMember.objects.filter(
                        team__workspace=workspace,
                        notes__contains=DEMO_KEY,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            set(FixtureOfficialAssignment.Status.values).issubset(
                set(
                    FixtureOfficialAssignment.objects.filter(
                        notes__contains=DEMO_KEY,
                        official__union=workspace.related_union,
                    ).values_list("status", flat=True)
                )
            )
        )
        self.assertTrue(
            UnionReviewComment.objects.filter(body__contains=DEMO_KEY).exists()
        )
        self.assertTrue(
            UnionDocumentReference.objects.filter(
                metadata__demo_key=DEMO_KEY,
            ).exists()
        )
        self.assertTrue(
            UnionAuditEvent.objects.filter(metadata__demo_key=DEMO_KEY).exists()
        )
        self.assertIn("Union workflow coverage seed complete.", output)

    def test_seed_is_idempotent(self):
        models = [
            ClubAffiliation,
            FixtureOfficialAssignment,
            NationalTeam,
            NationalTeamMember,
            UnionApproval,
            UnionAuditEvent,
            UnionDocumentReference,
            UnionPlayer,
            UnionPlayerCompetitionEligibility,
            UnionPlayerRegistration,
            UnionPlayerTransfer,
            UnionRegistrationApplication,
            UnionReviewComment,
        ]

        self.run_seed()
        before = {model._meta.label_lower: model.objects.count() for model in models}
        self.run_seed()
        after = {model._meta.label_lower: model.objects.count() for model in models}

        self.assertEqual(after, before)
