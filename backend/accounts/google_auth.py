"""Google OAuth authentication utilities for League OS."""

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleAuthException(Exception):
    """Base exception for Google authentication errors."""

    pass


class InvalidGoogleTokenError(GoogleAuthException):
    """Raised when the Google ID token is invalid or expired."""

    pass


class GoogleEmailNotVerifiedError(GoogleAuthException):
    """Raised when the Google account email is not verified."""

    pass


def verify_google_id_token(token: str) -> dict:
    """
    Verify a Google ID token and return the decoded payload.

    Uses the Google OAuth2 client ID from settings to verify the token.
    Returns the token payload dict which includes: sub, email, name,
    given_name, family_name, picture, etc.

    Raises:
        InvalidGoogleTokenError: If the token is invalid, expired, or
            the audience doesn't match.
        GoogleEmailNotVerifiedError: If the Google account email is
            not verified.

    Configuration (in settings.py / .env):
        GOOGLE_OAUTH2_CLIENT_ID - The OAuth 2.0 client ID from Google
            Cloud Console (required).
        GOOGLE_OAUTH2_CLIENT_SECRET - The OAuth 2.0 client secret
            (optional, used for server-side auth code flow).
    """
    client_id = getattr(settings, "GOOGLE_OAUTH2_CLIENT_ID", None)

    if not client_id:
        raise GoogleAuthException("GOOGLE_OAUTH2_CLIENT_ID is not configured.")

    try:
        # Verify the token against Google's public keys
        id_info = id_token.verify_oauth2_token(
            token, google_requests.Request(), client_id
        )
    except ValueError as exc:
        raise InvalidGoogleTokenError(f"Invalid Google ID token: {exc}") from exc

    # The token must have the correct audience (our client ID)
    if id_info.get("aud") != client_id:
        raise InvalidGoogleTokenError("Token audience does not match client ID.")

    # The issuer must be Google's accounts or Google's token endpoint
    valid_issuers = {"accounts.google.com", "https://accounts.google.com"}
    if id_info.get("iss") not in valid_issuers:
        raise InvalidGoogleTokenError(f"Invalid token issuer: {id_info.get('iss')}")

    # Require a verified email
    if not id_info.get("email_verified"):
        raise GoogleEmailNotVerifiedError("Google account email is not verified.")

    return id_info


def extract_google_user_info(payload: dict) -> dict:
    """
    Extract normalized user info from a verified Google token payload.

    Returns a dict with keys: email, first_name, last_name, avatar_url
    """
    email = payload.get("email", "").strip().lower()
    given_name = payload.get("given_name", "").strip()
    family_name = payload.get("family_name", "").strip()
    picture = payload.get("picture", "")

    # Use the name from Google if given_name/family_name is missing
    if not given_name and not family_name:
        full_name = payload.get("name", "").strip()
        parts = full_name.split(" ", 1)
        given_name = parts[0]
        if len(parts) > 1:
            family_name = parts[1]

    return {
        "email": email,
        "first_name": given_name,
        "last_name": family_name,
        "avatar_url": picture,
    }
