#!/usr/bin/env python
"""Django standalone script to list all user emails from the accounts app."""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from accounts.models import User  # noqa: E402

users = User.objects.all().order_by("email")

if not users.exists():
    print("No users found in the database.")
    sys.exit(0)

print(f"{'ID':<6} {'Email':<40} {'Role':<20} {'Verified'}")
print("-" * 90)
for user in users:
    print(
        f"{user.id:<6} {user.email:<40} {user.role:<20} "
        f"{'Yes' if user.is_email_verified else 'No'}"
    )

print(f"\nTotal: {users.count()} user(s)")
