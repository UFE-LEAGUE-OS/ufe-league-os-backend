from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom user manager for the League OS User model.

    The custom manager creates users using email instead of username.
    """

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a normal user like a fan/member account"""

        if not email:
            raise ValueError("Users must have an email address.")

        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return superuser (Django admin and League OS SUPER_ADMIN)"""

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "SUPER_ADMIN")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
