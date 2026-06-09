from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

# Create your tests here.

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        """Test confirms that normal users can becreated with email"""
        user = User.objects.create_user(
            email="fan@example.com",
            password="StrongPass123",
            first_name="Test",
            last_name="Fan",
        )

        self.assertEqual(user.email, "fan@example.com")
        self.assertTrue(user.check_password("StrongPass123"))
        self.assertEqual(user.role, User.Role.FAN)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_with_phone_number_successful(self):
        """Test confirms that phone numebrs can be saved"""
        user = User.objects.create_user(
            email="phoneuser@example.com",
            password="StrongPass123",
            first_name="Phone",
            last_name="User",
            phone_number="+256700000000",
        )

        self.assertEqual(user.phone_number, "+256700000000")

    def test_create_user_without_email_raises_error(self):
        """Test confirms that users cannot be created without email."""
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="",
                password="StrongPass123",
            )

    def test_create_superuser_successful(self):
        """Test confirms that super users can be created correctly."""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="StrongPass123",
            first_name="Admin",
            last_name="User",
        )

        self.assertEqual(user.email, "admin@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)

    def test_full_name_property(self):
        "Test confirms that full name property works"
        user = User.objects.create_user(
            email="kseruyange@email.com",
            password="StrongPass123",
            first_name="Keith",
            last_name="Seruyange",
        )

        self.assertEqual(user.full_name, "Keith Seruyange")


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_user_successful(self):
        payload = {
            "email": "newfan@example.com",
            "phone_number": "+256701000000",
            "first_name": "New",
            "last_name": "Fan",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }

        response = self.client.post(
            "/api/accounts/register/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["email"], payload["email"])
        self.assertEqual(response.data["user"]["role"], User.Role.FAN)
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            email="duplicate@example.com",
            phone_number="+256702000000",
            password="StrongPass123",
            first_name="Old",
            last_name="User",
        )

        payload = {
            "email": "duplicate@example.com",
            "phone_number": "+256703000000",
            "first_name": "New",
            "last_name": "User",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }

        response = self.client.post(
            "/api/accounts/register/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_register_rejects_duplicate_phone_number(self):
        User.objects.create_user(
            email="old-phone@example.com",
            phone_number="+256704000000",
            password="StrongPass123",
            first_name="Old",
            last_name="Phone",
        )

        payload = {
            "email": "new-phone@example.com",
            "phone_number": "0704000000",
            "first_name": "New",
            "last_name": "Phone",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }

        response = self.client.post(
            "/api/accounts/register/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)

    def test_login_with_email_successful(self):
        User.objects.create_user(
            email="login@example.com",
            phone_number="+256705000000",
            password="StrongPass123",
            first_name="Login",
            last_name="Email",
        )

        response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "login@example.com",
                "password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["role"], User.Role.FAN)
        self.assertEqual(response.data["dashboard_route"], "/dashboard/fan")

    def test_login_with_phone_number_successful(self):
        User.objects.create_user(
            email="phone-login@example.com",
            phone_number="+256706000000",
            password="StrongPass123",
            first_name="Login",
            last_name="Phone",
        )

        response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "+256706000000",
                "password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["phone_number"], "+256706000000")

    def test_login_with_local_phone_number_format_successful(self):
        User.objects.create_user(
            email="local-phone@example.com",
            phone_number="+256707000000",
            password="StrongPass123",
            first_name="Local",
            last_name="Phone",
        )

        response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "0707000000",
                "password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_login_with_invalid_credentials_fails(self):
        User.objects.create_user(
            email="wrong-password@example.com",
            phone_number="+256708000000",
            password="StrongPass123",
            first_name="Wrong",
            last_name="Password",
        )

        response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "wrong-password@example.com",
                "password": "WrongPassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_me_endpoint_returns_authenticated_user(self):
        user = User.objects.create_user(
            email="me@example.com",
            phone_number="+256709000000",
            password="StrongPass123",
            first_name="Current",
            last_name="User",
        )

        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "me@example.com",
                "password": "StrongPass123",
            },
            format="json",
        )

        access_token = login_response.data["access"]

        response = self.client.get(
            "/api/accounts/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], user.email)
