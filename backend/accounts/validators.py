"""
Custom password validators for the accounts app.

Provides AdvancedStrengthValidator which enforces:
- No emojis or non-standard characters (ASCII printable only)
- Minimum length of 12 characters
- zxcvbn strength score >= 2
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

try:
    from zxcvbn import zxcvbn
except ImportError:
    zxcvbn = None


class AdvancedStrengthValidator:
    """
    A Django password validator that enforces:
      1. Only ASCII printable characters (no emojis, no non-standard chars).
      2. Minimum length of 12 characters.
      3. zxcvbn strength score >= 2.

    The validator is intentionally strict about character range to block
    emojis, zero-width joiners, right-to-left marks, etc.
    """

    MIN_LENGTH = 12
    MIN_ZXCVBN_SCORE = 2

    def __init__(self, min_length=None, min_zxcvbn_score=None):
        self.min_length = min_length or self.MIN_LENGTH
        self.min_zxcvbn_score = min_zxcvbn_score or self.MIN_ZXCVBN_SCORE

    def validate(self, password, user=None):
        # 1. Block emojis and non-standard characters
        if not re.match(r"^[\x20-\x7E]*$", password):
            raise ValidationError(
                _(
                    "Password must contain only standard keyboard characters "
                    "(no emojis or special symbols)."
                ),
                code="password_non_standard_chars",
            )

        # 2. Enforce minimum length
        if len(password) < self.min_length:
            raise ValidationError(
                _(
                    "This password is too short. "
                    "It must contain at least %(min_length)d characters."
                ),
                code="password_too_short",
                params={"min_length": self.min_length},
            )

        # 3. Run zxcvbn strength check
        if zxcvbn is None:
            return  # skip if library not available

        result = zxcvbn(password)
        score = result.get("score", 0)

        if score < self.min_zxcvbn_score:
            feedback = result.get("feedback", {})
            suggestions = feedback.get("suggestions", [])
            warning = feedback.get("warning", "")

            messages = [_("This password is too weak. Please choose a stronger one.")]
            if warning:
                messages.append(warning)
            messages.extend(suggestions)

            raise ValidationError(
                " ".join(messages),
                code="password_too_weak",
            )

    def get_help_text(self):
        return _(
            "Your password must be at least %(min_length)d characters "
            "long, use only standard keyboard characters, and not be "
            "too common or easy to guess."
        ) % {"min_length": self.min_length}
