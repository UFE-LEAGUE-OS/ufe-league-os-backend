from django.contrib.auth import get_user_model
from django.test import TestCase

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
