from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from accounts.models import Club, User
from dashboards.models import Match, Competition, League, Union
from sponsorships.models import (
    SponsorAccount,
    SponsorPackage,
    SponsorshipOwnerType,
    SponsorshipScopeType,
)
from .models import (
    ClubDocument,
    ClubOperationAuditLog,
    ComplianceChecklist,
    SponsorCampaign,
    MatchdayOperationTask,
    TicketingOfficerAssignment,
    MatchdayReport,
)
from .services import mark_expired_documents, update_overdue_compliance_tasks


class ClubOperationsServiceTests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="clubadmin2@example.com",
            password="testpass123",
            first_name="Club",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Test Club 2", slug="test-club-2", admin=self.club_admin
        )

    def test_mark_expired_documents(self):
        dummy_file = SimpleUploadedFile(
            "expired.pdf", b"file_content", content_type="application/pdf"
        )
        ClubDocument.objects.create(
            club=self.club,
            title="Expired Doc",
            category=ClubDocument.Category.CONSTITUTION,
            file=dummy_file,
            uploaded_by=self.club_admin,
            expiry_date="2000-01-01",
        )
        mark_expired_documents()
        self.assertEqual(
            ClubDocument.objects.filter(status=ClubDocument.Status.EXPIRED).count(), 1
        )

    def test_update_overdue_compliance_tasks(self):
        ComplianceChecklist.objects.create(
            club=self.club,
            title="Overdue Task",
            category="Governance",
            due_date="2000-01-01",
            status=ComplianceChecklist.Status.PENDING,
        )
        update_overdue_compliance_tasks()
        self.assertEqual(
            ComplianceChecklist.objects.filter(
                status=ComplianceChecklist.Status.OVERDUE
            ).count(),
            1,
        )


class SponsorCampaignAPITests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="campaignadmin@example.com",
            password="testpass123",
            first_name="Campaign",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Campaign Club", slug="campaign-club", admin=self.club_admin
        )
        self.super_admin = User.objects.create_user(
            email="superadmin@example.com",
            password="testpass123",
            first_name="Super",
            last_name="Admin",
            role=User.Role.SUPER_ADMIN,
            is_email_verified=True,
        )
        self.sponsor = SponsorAccount.objects.create(
            owner=self.club_admin,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Test Sponsor",
            brn="C12345",
            tin="T12345",
        )
        self.package = SponsorPackage.objects.create(
            name="Test Package",
            owner_type=SponsorshipOwnerType.CLUB,
            owner_identifier="CLUB",
            owner_name="Club",
            scope_type=SponsorshipScopeType.CLUB,
            scope_identifier="CLUB",
            scope_name="Club",
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_create_campaign(self):
        response = self.client.post(
            "/api/club/sponsor-campaigns/",
            {
                "sponsor": self.sponsor.id,
                "sponsor_package": self.package.id,
                "name": "Test Campaign",
                "description": "Test description",
                "objective": "Reach more fans",
                "campaign_type": SponsorCampaign.CampaignType.MATCHDAY,
                "status": SponsorCampaign.CampaignStatus.DRAFT,
                "start_date": (timezone.now() + timedelta(days=1)).isoformat(),
                "end_date": (timezone.now() + timedelta(days=30)).isoformat(),
                "budget": 500000,
                "expected_reach": 1000,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(SponsorCampaign.objects.count(), 1)
        self.assertTrue(
            ClubOperationAuditLog.objects.filter(
                action=ClubOperationAuditLog.ActionType.CAMPAIGN_CREATED
            ).exists()
        )

    def test_list_campaigns(self):
        SponsorCampaign.objects.create(
            club=self.club,
            sponsor=self.sponsor,
            name="Campaign 1",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=10),
            created_by=self.club_admin,
        )
        response = self.client.get("/api/club/sponsor-campaigns/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_campaign_soft_delete(self):
        campaign = SponsorCampaign.objects.create(
            club=self.club,
            sponsor=self.sponsor,
            name="To Delete",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=10),
            created_by=self.club_admin,
        )
        response = self.client.delete(f"/api/club/sponsor-campaigns/{campaign.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        campaign.refresh_from_db()
        self.assertTrue(campaign.is_deleted)
        self.assertIsNotNone(campaign.deleted_at)

    def test_campaign_archive(self):
        campaign = SponsorCampaign.objects.create(
            club=self.club,
            sponsor=self.sponsor,
            name="To Archive",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=10),
            created_by=self.club_admin,
        )
        response = self.client.post(
            f"/api/club/sponsor-campaigns/{campaign.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, SponsorCampaign.CampaignStatus.ARCHIVED)

    def test_fan_cannot_access_campaigns(self):
        fan = User.objects.create_user(
            email="fan@example.com",
            password="testpass123",
            first_name="Fan",
            last_name="User",
            role=User.Role.FAN,
            is_email_verified=True,
        )
        self.client.force_authenticate(user=fan)
        response = self.client.get("/api/club/sponsor-campaigns/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CampaignAssignmentAPITests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="assignmentadmin@example.com",
            password="testpass123",
            first_name="Assignment",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Assignment Club", slug="assignment-club", admin=self.club_admin
        )
        self.sponsor = SponsorAccount.objects.create(
            owner=self.club_admin,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Test Sponsor",
            brn="C12345",
            tin="T12345",
        )
        self.campaign = SponsorCampaign.objects.create(
            club=self.club,
            sponsor=self.sponsor,
            name="Assignment Campaign",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            created_by=self.club_admin,
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_create_assignment(self):
        union = Union.objects.create(name="Test Union", slug="test-union")
        league = League.objects.create(
            union=union, name="Test League", slug="test-league"
        )
        competition = Competition.objects.create(
            league=league, name="Test Competition", slug="test-competition"
        )
        match = Match.objects.create(
            home_club=self.club,
            away_club=Club.objects.create(name="Away Club", slug="away-club"),
            match_date=timezone.now() + timedelta(days=7),
            competition=competition,
        )
        response = self.client.post(
            "/api/club/campaign-assignments/",
            {
                "campaign": self.campaign.id,
                "match": match.id,
                "activation_notes": "Test activation",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class MatchdayTaskAPITests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="taskadmin@example.com",
            password="testpass123",
            first_name="Task",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Task Club", slug="task-club", admin=self.club_admin
        )
        union = Union.objects.create(name="Task Union", slug="task-union")
        league = League.objects.create(
            union=union, name="Task League", slug="task-league"
        )
        competition = Competition.objects.create(
            league=league, name="Task Competition", slug="task-competition"
        )
        self.match = Match.objects.create(
            home_club=self.club,
            away_club=Club.objects.create(name="Away Club 2", slug="away-club-2"),
            match_date=timezone.now() + timedelta(days=7),
            competition=competition,
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_create_task(self):
        response = self.client.post(
            "/api/club/matchday-tasks/",
            {
                "club": self.club.id,
                "match": self.match.id,
                "title": "Security Setup",
                "description": "Setup security",
                "category": MatchdayOperationTask.TaskCategory.SECURITY,
                "priority": MatchdayOperationTask.Priority.HIGH,
                "due_date": (timezone.now() + timedelta(days=3)).date().isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_complete_task(self):
        task = MatchdayOperationTask.objects.create(
            club=self.club,
            match=self.match,
            title="Setup Task",
            category=MatchdayOperationTask.TaskCategory.STADIUM_PREP,
            priority=MatchdayOperationTask.Priority.MEDIUM,
            due_date=timezone.now().date() + timedelta(days=3),
            created_by=self.club_admin,
            assigned_to=self.club_admin,
        )
        response = self.client.post(f"/api/club/matchday-tasks/{task.id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, MatchdayOperationTask.TaskStatus.COMPLETED)


class TicketingOfficerAPITests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="officeradmin@example.com",
            password="testpass123",
            first_name="Officer",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Officer Club", slug="officer-club", admin=self.club_admin
        )
        self.officer = User.objects.create_user(
            email="officer@example.com",
            password="testpass123",
            first_name="Ticket",
            last_name="Officer",
            role=User.Role.CLUB_ADMIN,
            club=self.club,
            is_email_verified=True,
        )
        union = Union.objects.create(name="Officer Union", slug="officer-union")
        league = League.objects.create(
            union=union, name="Officer League", slug="officer-league"
        )
        competition = Competition.objects.create(
            league=league, name="Officer Competition", slug="officer-competition"
        )
        self.match = Match.objects.create(
            home_club=self.club,
            away_club=Club.objects.create(name="Away Club 3", slug="away-club-3"),
            match_date=timezone.now() + timedelta(days=7),
            competition=competition,
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_assign_officer(self):
        response = self.client.post(
            "/api/club/ticketing-officers/",
            {
                "club": self.club.id,
                "match": self.match.id,
                "officer": self.officer.id,
                "assignment_role": TicketingOfficerAssignment.AssignmentRole.TICKET_SCANNER,
                "gate_allocation": "Gate A",
                "shift_start": (timezone.now() + timedelta(days=1)).isoformat(),
                "shift_end": (timezone.now() + timedelta(days=1, hours=8)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_prevent_different_club_officer(self):
        other_club = Club.objects.create(name="Other Club", slug="other-club")
        other_officer = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            first_name="Other",
            last_name="Officer",
            role=User.Role.CLUB_ADMIN,
            club=other_club,
            is_email_verified=True,
        )
        response = self.client.post(
            "/api/club/ticketing-officers/",
            {
                "club": self.club.id,
                "match": self.match.id,
                "officer": other_officer.id,
                "assignment_role": TicketingOfficerAssignment.AssignmentRole.TICKET_SCANNER,
                "gate_allocation": "Gate A",
                "shift_start": (timezone.now() + timedelta(days=1)).isoformat(),
                "shift_end": (timezone.now() + timedelta(days=1, hours=8)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MatchdayReportAPITests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="reportadmin@example.com",
            password="testpass123",
            first_name="Report",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Report Club", slug="report-club", admin=self.club_admin
        )
        union = Union.objects.create(name="Report Union", slug="report-union")
        league = League.objects.create(
            union=union, name="Report League", slug="report-league"
        )
        competition = Competition.objects.create(
            league=league, name="Report Competition", slug="report-competition"
        )
        self.match = Match.objects.create(
            home_club=self.club,
            away_club=Club.objects.create(name="Away Club 4", slug="away-club-4"),
            match_date=timezone.now() + timedelta(days=7),
            competition=competition,
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_create_draft_report(self):
        response = self.client.post(
            "/api/club/matchday-reports/",
            {
                "match": self.match.id,
                "attendance_tickets_sold": 500,
                "revenue_ticket": 2500000,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], MatchdayReport.ReportStatus.DRAFT)

    def test_submit_report(self):
        report = MatchdayReport.objects.create(
            match=self.match,
            club=self.club,
            submitted_by=self.club_admin,
            status=MatchdayReport.ReportStatus.DRAFT,
        )
        response = self.client.post(f"/api/club/matchday-reports/{report.id}/submit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, MatchdayReport.ReportStatus.SUBMITTED)
        self.assertIsNotNone(report.submitted_at)

    def test_approve_report(self):
        report = MatchdayReport.objects.create(
            match=self.match,
            club=self.club,
            submitted_by=self.club_admin,
            status=MatchdayReport.ReportStatus.SUBMITTED,
            submitted_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.post(f"/api/club/matchday-reports/{report.id}/approve/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, MatchdayReport.ReportStatus.APPROVED)


class ClubOperationAuditLogTests(APITestCase):
    def test_audit_log_created_on_campaign_create(self):
        club_admin = User.objects.create_user(
            email="auditadmin@example.com",
            password="testpass123",
            first_name="Audit",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        club = Club.objects.create(
            name="Audit Club", slug="audit-club", admin=club_admin
        )
        sponsor = SponsorAccount.objects.create(
            owner=club_admin,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Audit Sponsor",
            brn="A12345",
            tin="T54321",
        )
        self.client.force_authenticate(user=club_admin)
        response = self.client.post(
            "/api/club/sponsor-campaigns/",
            {
                "sponsor": sponsor.id,
                "name": "Audit Campaign",
                "campaign_type": SponsorCampaign.CampaignType.MATCHDAY,
                "status": SponsorCampaign.CampaignStatus.DRAFT,
                "start_date": (timezone.now() + timedelta(days=1)).isoformat(),
                "end_date": (timezone.now() + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(ClubOperationAuditLog.objects.count(), 1)
        log = ClubOperationAuditLog.objects.first()
        self.assertEqual(log.action, ClubOperationAuditLog.ActionType.CAMPAIGN_CREATED)
        self.assertEqual(log.club, club)
        self.assertEqual(log.user, club_admin)
