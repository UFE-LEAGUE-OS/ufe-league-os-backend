"""Shared account attachment/provisioning for governance scopes."""

import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def provision_or_attach_user(*, account):
    User = get_user_model()
    email = account["email"].strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        if not user.is_active:
            raise ValidationError({"email": "The selected user is inactive."})
        changed = []
        for field in ("first_name", "last_name", "phone_number"):
            value = account.get(field)
            if value and not getattr(user, field):
                setattr(user, field, value)
                changed.append(field)
        if changed:
            user.save(update_fields=changed)
        return user, False, None

    password = account.get("password") or f"LeagueOS-{secrets.token_urlsafe(10)}A1!"
    candidate = User(
        email=email,
        first_name=account.get("first_name") or "League",
        last_name=account.get("last_name") or "Administrator",
        phone_number=account.get("phone_number") or None,
        role=User.Role.FAN,
        is_email_verified=True,
    )
    validate_password(password, candidate)
    user = User.objects.create_user(
        email=candidate.email,
        password=password,
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        phone_number=candidate.phone_number,
        role=User.Role.FAN,
        is_email_verified=True,
    )
    return user, True, password
