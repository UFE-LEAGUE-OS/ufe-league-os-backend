from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Create a super admin user"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Super admin email")
        parser.add_argument("--password", required=True, help="Super admin password")
        parser.add_argument("--first-name", default="Super", help="First name")
        parser.add_argument("--last-name", default="Admin", help="Last name")

    def handle(self, *args, **options):
        self.stdout.write("Running migrations...")
        call_command("migrate", verbosity=0)

        User = get_user_model()
        email = options["email"]
        password = options["password"]
        first_name = options["first_name"]
        last_name = options["last_name"]

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f"User with email {email} already exists.")
            )
            return

        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.SUPER_ADMIN,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Super admin created successfully: {user.email} (role={user.role})"
            )
        )
