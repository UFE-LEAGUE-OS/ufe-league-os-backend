from rest_framework.test import APITestCase

from accounts.models import Club, User
from .models import ClubDocument, ComplianceChecklist
from .services import mark_expired_documents, update_overdue_compliance_tasks


class ClubOperationsTests(APITestCase):
    def setUp(self):
        self.club_admin = User.objects.create_user(
            email="clubadmin@example.com",
            password="testpass123",
            first_name="Club",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
            is_email_verified=True,
        )
        self.club = Club.objects.create(
            name="Test Club", slug="test-club", admin=self.club_admin
        )
        self.super_admin = User.objects.create_user(
            email="super@example.com",
            password="testpass123",
            first_name="Super",
            last_name="Admin",
            role=User.Role.SUPER_ADMIN,
            is_email_verified=True,
        )
        self.fan = User.objects.create_user(
            email="fan@example.com",
            password="testpass123",
            first_name="Fan",
            last_name="User",
            role=User.Role.FAN,
            is_email_verified=True,
        )
        self.client.force_authenticate(user=self.club_admin)

    def test_document_crud(self):
        response = self.client.post(
            "/api/club/documents/",
            {
                "title": "Constitution",
                "category": ClubDocument.Category.CONSTITUTION,
                "club": self.club.id,
            },
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get("/api/club/documents/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_communication_logs_read_only(self):
        response = self.client.post("/api/club/communications/", {})
        self.assertEqual(response.status_code, 405)

    def test_fan_cannot_access_documents(self):
        self.client.force_authenticate(user=self.fan)
        response = self.client.get("/api/club/documents/")
        self.assertEqual(response.status_code, 403)

    def test_super_admin_can_access_club_documents(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/club/documents/")
        self.assertEqual(response.status_code, 200)

    def test_compliance_task_lifecycle(self):
        response = self.client.post(
            "/api/club/compliance/",
            {
                "club": self.club.id,
                "title": "Annual Return",
                "category": "Governance",
                "due_date": "2099-12-31",
                "priority": ComplianceChecklist.Priority.HIGH,
            },
        )
        self.assertEqual(response.status_code, 201)
        item_id = response.data["id"]

        response = self.client.post(f"/api/club/compliance/{item_id}/complete/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["completed"])

        response = self.client.post(f"/api/club/compliance/{item_id}/reopen/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["completed"])


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
        ClubDocument.objects.create(
            club=self.club,
            title="Expired Doc",
            category=ClubDocument.Category.CONSTITUTION,
            file="fake.pdf",
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
