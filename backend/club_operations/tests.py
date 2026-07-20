from rest_framework.test import APITestCase

from accounts.models import Club, User
from .models import ClubDocument


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
                "file": "fake.pdf",
            },
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get("/api/club/documents/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_communication_logs_read_only(self):
        response = self.client.post("/api/club/communications/", {})
        self.assertEqual(response.status_code, 405)
