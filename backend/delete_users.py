#!/usr/bin/env python
"""Django standalone script to delete users by email address."""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from accounts.models import User


def delete_users_by_email(emails):
    """Delete users with the given email addresses."""
    if not emails:
        print("No email addresses provided.")
        print("Usage: python delete_users.py email1@example.com email2@example.com")
        sys.exit(1)

    deleted = []
    not_found = []

    for email in emails:
        try:
            user = User.objects.get(email=email)
            username = user.email
            user.delete()
            deleted.append(username)
            print(f"Deleted: {username}")
        except User.DoesNotExist:
            not_found.append(email)
            print(f"Not found: {email}")

    print(f"\nSummary:")
    print(f"  Deleted: {len(deleted)} user(s)")
    print(f"  Not found: {len(not_found)} user(s)")

    if deleted:
        print(f"\nDeleted emails: {', '.join(deleted)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete_users.py email1@example.com email2@example.com")
        print("\nExample:")
        print("  python delete_users.py test@example.com old@example.com")
        sys.exit(1)

    emails = sys.argv[1:]
    delete_users_by_email(emails)
