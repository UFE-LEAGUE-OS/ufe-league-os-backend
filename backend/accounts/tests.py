import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import EmailOTP

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()

SMALL_GIF_IMAGE = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class UserModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        """Test confirms that normal users can be created with email."""
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
        """Test confirms that phone numbers can be saved."""
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
        """Test confirms that full name property works."""
        user = User.objects.create_user(
            email="kseruyange@email.com",
            password="StrongPass123",
            first_name="Keith",
            last_name="Seruyange",
        )

        self.assertEqual(user.full_name, "Keith Seruyange")


@override_settings(PRINT_DEV_OTPS=False)
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
        self.assertTrue(response.data["requires_email_verification"])
        self.assertEqual(response.data["next_step"], "VERIFY_EMAIL")
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
        user = User.objects.create_user(
            email="login@example.com",
            phone_number="+256705000000",
            password="StrongPass123",
            first_name="Login",
            last_name="Email",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

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
        self.assertEqual(response.data["frontend_dashboard_route"], "/dashboard/fan")
        self.assertEqual(response.data["next_step"], "DASHBOARD")

    def test_login_with_phone_number_successful(self):
        user = User.objects.create_user(
            email="phone-login@example.com",
            phone_number="+256706000000",
            password="StrongPass123",
            first_name="Login",
            last_name="Phone",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

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
        user = User.objects.create_user(
            email="local-phone@example.com",
            phone_number="+256707000000",
            password="StrongPass123",
            first_name="Local",
            last_name="Phone",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

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

    def test_unverified_user_cannot_login_and_receives_no_tokens(self):
        User.objects.create_user(
            email="unverified-login@example.com",
            phone_number="+256715000000",
            password="StrongPass123",
            first_name="Unverified",
            last_name="User",
        )

        response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": "unverified-login@example.com",
                "password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "email_not_verified")
        self.assertTrue(response.data["requires_email_verification"])
        self.assertEqual(response.data["next_step"], "VERIFY_EMAIL")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_me_endpoint_returns_authenticated_user(self):
        user = User.objects.create_user(
            email="me@example.com",
            phone_number="+256709000000",
            password="StrongPass123",
            first_name="Current",
            last_name="User",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

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

    def test_register_creates_email_otp(self):
        payload = {
            "email": "otpuser@example.com",
            "phone_number": "+256710000000",
            "first_name": "Otp",
            "last_name": "User",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }

        response = self.client.post(
            "/api/accounts/register/",
            payload,
            format="json",
        )

        user = User.objects.get(email=payload["email"])

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            EmailOTP.objects.filter(
                user=user,
                purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
                is_used=False,
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SEND_OTP_EMAILS=True,
        PRINT_DEV_OTPS=False,
        DEFAULT_FROM_EMAIL="League OS <noreply@testserver.local>",
    )
    def test_register_sends_email_otp_when_enabled(self):
        mail.outbox = []

        payload = {
            "email": "otp-email-send@example.com",
            "phone_number": "+256710000001",
            "first_name": "Otp",
            "last_name": "Email",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }

        response = self.client.post(
            "/api/accounts/register/",
            payload,
            format="json",
        )

        user = User.objects.get(email=payload["email"])
        otp = EmailOTP.objects.get(
            user=user,
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            is_used=False,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertEqual(email.subject, "Verify your League OS email address")
        self.assertEqual(email.to, [payload["email"]])
        self.assertIn("Hello Otp", email.body)
        self.assertIn("email verification code", email.body)
        self.assertIn(otp.code, email.body)

    def test_verify_email_otp_successful(self):
        user = User.objects.create_user(
            email="verify@example.com",
            phone_number="+256711000000",
            password="StrongPass123",
            first_name="Verify",
            last_name="User",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": otp.code,
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        user.refresh_from_db()
        otp.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(otp.is_used)
        self.assertFalse(response.data["requires_email_verification"])
        self.assertEqual(response.data["next_step"], "LOG_IN")

    def test_verify_email_otp_with_invalid_code_fails(self):
        user = User.objects.create_user(
            email="invalid-otp@example.com",
            phone_number="+256712000000",
            password="StrongPass123",
            first_name="Invalid",
            last_name="Otp",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": "000000",
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        user.refresh_from_db()
        otp.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(otp.attempts, 1)

    def test_verify_email_otp_with_expired_code_fails(self):
        user = User.objects.create_user(
            email="expired-otp@example.com",
            phone_number="+256713000000",
            password="StrongPass123",
            first_name="Expired",
            last_name="Otp",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )

        response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": otp.code,
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        user.refresh_from_db()
        otp.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(user.is_email_verified)
        self.assertTrue(otp.is_used)

    def test_resend_email_otp_successful(self):
        user = User.objects.create_user(
            email="resend@example.com",
            phone_number="+256714000000",
            password="StrongPass123",
            first_name="Resend",
            last_name="Otp",
        )

        response = self.client.post(
            "/api/accounts/resend-otp/",
            {
                "email": user.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EmailOTP.objects.filter(
                user=user,
                purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
                is_used=False,
            ).exists()
        )
        self.assertEqual(response.data["next_step"], "VERIFY_EMAIL")

    def test_password_reset_request_creates_password_reset_otp(self):
        user = User.objects.create_user(
            email="reset-request@example.com",
            phone_number="+256730000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Request",
        )

        response = self.client.post(
            "/api/accounts/password-reset/request/",
            {
                "email": user.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EmailOTP.objects.filter(
                user=user,
                purpose=EmailOTP.Purpose.PASSWORD_RESET,
                is_used=False,
            ).exists()
        )
        self.assertEqual(response.data["next_step"], "RESET_PASSWORD")

    def test_password_reset_request_rejects_unknown_email(self):
        response = self.client.post(
            "/api/accounts/password-reset/request/",
            {
                "email": "missing-user@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_password_reset_confirm_successful(self):
        user = User.objects.create_user(
            email="reset-confirm@example.com",
            phone_number="+256731000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Confirm",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": otp.code,
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        user.refresh_from_db()
        otp.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["next_step"], "LOG_IN")
        self.assertTrue(user.check_password("NewStrongPass123"))
        self.assertTrue(otp.is_used)

    def test_user_can_login_with_new_password_after_password_reset(self):
        user = User.objects.create_user(
            email="reset-login@example.com",
            phone_number="+256732000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Login",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        reset_response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": otp.code,
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        self.assertEqual(reset_response.status_code, 200)

        old_login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": "OldStrongPass123",
            },
            format="json",
        )

        self.assertEqual(old_login_response.status_code, 400)

        new_login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": "NewStrongPass123",
            },
            format="json",
        )

        self.assertEqual(new_login_response.status_code, 200)
        self.assertIn("access", new_login_response.data)
        self.assertIn("refresh", new_login_response.data)
        self.assertEqual(new_login_response.data["next_step"], "DASHBOARD")

    def test_password_reset_confirm_rejects_invalid_otp_and_increments_attempts(self):
        user = User.objects.create_user(
            email="reset-invalid@example.com",
            phone_number="+256733000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Invalid",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": "000000",
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        otp.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        self.assertEqual(otp.attempts, 1)
        self.assertTrue(user.check_password("OldStrongPass123"))

    def test_password_reset_confirm_rejects_expired_otp(self):
        user = User.objects.create_user(
            email="reset-expired@example.com",
            phone_number="+256734000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Expired",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )

        response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": otp.code,
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        otp.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        self.assertTrue(otp.is_used)
        self.assertTrue(user.check_password("OldStrongPass123"))

    def test_used_password_reset_otp_cannot_be_reused(self):
        user = User.objects.create_user(
            email="reset-reuse@example.com",
            phone_number="+256735000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Reuse",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        first_response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": otp.code,
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": otp.code,
                "password": "AnotherStrongPass123",
                "confirm_password": "AnotherStrongPass123",
            },
            format="json",
        )

        user.refresh_from_db()

        self.assertEqual(second_response.status_code, 400)
        self.assertIn("code", second_response.data)
        self.assertTrue(user.check_password("NewStrongPass123"))

    def test_resend_email_otp_invalidates_previous_unused_otp(self):
        user = User.objects.create_user(
            email="resend-invalidates@example.com",
            phone_number="+256736000000",
            password="StrongPass123",
            first_name="Resend",
            last_name="Invalidates",
        )

        old_otp = EmailOTP.objects.create(
            user=user,
            code="111111",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/resend-otp/",
            {
                "email": user.email,
            },
            format="json",
        )

        old_otp.refresh_from_db()

        active_otps = EmailOTP.objects.filter(
            user=user,
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            is_used=False,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(old_otp.is_used)
        self.assertEqual(active_otps.count(), 1)
        self.assertNotEqual(active_otps.first().code, old_otp.code)

    def test_resend_email_otp_rejects_already_verified_user(self):
        user = User.objects.create_user(
            email="already-verified@example.com",
            phone_number="+256737000000",
            password="StrongPass123",
            first_name="Verified",
            last_name="User",
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        response = self.client.post(
            "/api/accounts/resend-otp/",
            {
                "email": user.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_used_email_verification_otp_cannot_be_reused(self):
        user = User.objects.create_user(
            email="reuse-email-otp@example.com",
            phone_number="+256738000000",
            password="StrongPass123",
            first_name="Reuse",
            last_name="Otp",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        first_response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": otp.code,
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        second_response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": otp.code,
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        otp.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(otp.is_used)
        self.assertEqual(second_response.status_code, 400)
        self.assertIn("code", second_response.data)

    @override_settings(OTP_MAX_ATTEMPTS=2)
    def test_email_verification_otp_locks_after_max_attempts(self):
        user = User.objects.create_user(
            email="email-max-attempts@example.com",
            phone_number="+256739000000",
            password="StrongPass123",
            first_name="Max",
            last_name="Attempts",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.EMAIL_VERIFICATION,
            attempts=1,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/verify-otp/",
            {
                "email": user.email,
                "code": "000000",
                "purpose": "EMAIL_VERIFICATION",
            },
            format="json",
        )

        otp.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        self.assertEqual(otp.attempts, 2)
        self.assertTrue(otp.is_used)
        self.assertFalse(user.is_email_verified)

    @override_settings(OTP_MAX_ATTEMPTS=2)
    def test_password_reset_otp_locks_after_max_attempts(self):
        user = User.objects.create_user(
            email="reset-max-attempts@example.com",
            phone_number="+256740000000",
            password="OldStrongPass123",
            first_name="Reset",
            last_name="Attempts",
        )

        otp = EmailOTP.objects.create(
            user=user,
            code="123456",
            purpose=EmailOTP.Purpose.PASSWORD_RESET,
            attempts=1,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "email": user.email,
                "code": "000000",
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            },
            format="json",
        )

        otp.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)
        self.assertEqual(otp.attempts, 2)
        self.assertTrue(otp.is_used)
        self.assertTrue(user.check_password("OldStrongPass123"))


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProfileAPITests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="profile@example.com",
            phone_number="+256720000000",
            password="StrongPass123",
            first_name="Profile",
            last_name="User",
        )
        self.user.is_email_verified = True
        self.user.save(update_fields=["is_email_verified"])

        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": self.user.email,
                "password": "StrongPass123",
            },
            format="json",
        )

        self.access_token = login_response.data["access"]
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

    def test_profile_endpoint_requires_authentication(self):
        unauthenticated_client = APIClient()

        response = unauthenticated_client.get("/api/accounts/profile/")

        self.assertEqual(response.status_code, 401)

    def test_get_profile_successful(self):
        response = self.client.get("/api/accounts/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user.email)

    def test_update_profile_successful(self):
        response = self.client.patch(
            "/api/accounts/profile/",
            {
                "first_name": "Updated",
                "last_name": "Name",
                "phone_number": "0721000000",
            },
            format="json",
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.phone_number, "+256721000000")
        self.assertEqual(response.data["user"]["full_name"], "Updated Name")

    def test_update_profile_rejects_duplicate_phone_number(self):
        User.objects.create_user(
            email="other@example.com",
            phone_number="+256722000000",
            password="StrongPass123",
            first_name="Other",
            last_name="User",
        )

        response = self.client.patch(
            "/api/accounts/profile/",
            {
                "phone_number": "0722000000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)

    def test_upload_avatar_successful(self):
        avatar = SimpleUploadedFile(
            "avatar.gif",
            SMALL_GIF_IMAGE,
            content_type="image/gif",
        )

        response = self.client.patch(
            "/api/accounts/profile/",
            {
                "avatar": avatar,
            },
            format="multipart",
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(bool(self.user.avatar))
        self.assertIsNotNone(response.data["user"]["avatar_url"])

    def test_upload_avatar_rejects_large_file(self):
        large_image = SimpleUploadedFile(
            "large-avatar.gif",
            SMALL_GIF_IMAGE + (b"0" * ((2 * 1024 * 1024) + 1)),
            content_type="image/gif",
        )

        response = self.client.patch(
            "/api/accounts/profile/",
            {
                "avatar": large_image,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.data)

    def test_remove_avatar_successful(self):
        avatar = SimpleUploadedFile(
            "avatar.gif",
            SMALL_GIF_IMAGE,
            content_type="image/gif",
        )

        upload_response = self.client.patch(
            "/api/accounts/profile/",
            {
                "avatar": avatar,
            },
            format="multipart",
        )

        self.assertEqual(upload_response.status_code, 200)

        response = self.client.delete("/api/accounts/profile/avatar/")

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(bool(self.user.avatar))
        self.assertIsNone(response.data["user"]["avatar_url"])
