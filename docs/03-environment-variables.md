# 03. Environment Variables

The backend uses `.env` for local development and platform environment variables for staging/production.

Start by copying:

```bash
cp .env.example .env
```

Never commit real secrets.

## Core Django Settings

| Variable | Local Example | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | development secret | Django signing key. Must be secret in production. |
| `DJANGO_DEBUG` | `True` | Enable debug locally. Must be `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Hosts allowed to serve the app. Add Render domain in staging. |

## Database Settings

For Docker local development:

| Variable | Local Value |
|---|---|
| `DB_NAME` | `league_os` |
| `DB_USER` | `league_os_user` |
| `DB_PASSWORD` | `league_os_password` |
| `DB_HOST` | `db` |
| `DB_PORT` | `5432` |

PostgreSQL container values:

| Variable | Local Value |
|---|---|
| `POSTGRES_DB` | `league_os` |
| `POSTGRES_USER` | `league_os_user` |
| `POSTGRES_PASSWORD` | `league_os_password` |

For Render/Neon/staging, use:

```env
DATABASE_URL=postgresql://...
```

When `DATABASE_URL` is set, Django uses `dj-database-url`.

## CORS and CSRF

For local frontend:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173
```

For staging, include the deployed frontend URL:

```env
CORS_ALLOWED_ORIGINS=https://ufe-league-os-frontend.onrender.com
CSRF_TRUSTED_ORIGINS=https://ufe-league-os-frontend.onrender.com
```

## Email / OTP

Local development recommended:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SEND_OTP_EMAILS=False
PRINT_DEV_OTPS=True
```

This prints OTPs in backend logs instead of sending real emails.

For Render/Brevo staging:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SEND_OTP_EMAILS=True
PRINT_DEV_OTPS=False
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=2525
EMAIL_HOST_USER=<brevo-smtp-login>
EMAIL_HOST_PASSWORD=<brevo-smtp-key>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=League OS <verified-sender@example.com>
SERVER_EMAIL=League OS <verified-sender@example.com>
```

## Google OAuth

```env
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret
```

The backend requires `google-auth` in `backend/requirements.txt`.

## Flutterwave Settings

Used by sponsorships and ticketing.

```env
FLUTTERWAVE_MODE=test
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your-test-public-key
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your-test-secret-key
FLUTTERWAVE_SECRET_HASH=replace-with-random-test-webhook-secret
FLUTTERWAVE_TIMEOUT_SECONDS=30
```

Sponsorship redirect:

```env
FLUTTERWAVE_REDIRECT_URL=http://localhost:8000/api/sponsorships/flutterwave/verify/
FLUTTERWAVE_PAYMENT_TITLE=League OS Sponsorship Payment
```

Ticketing redirect:

```env
FLUTTERWAVE_TICKET_REDIRECT_URL=http://localhost:8000/api/ticketing/flutterwave/verify/
FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment
```

Optional logo:

```env
FLUTTERWAVE_PAYMENT_LOGO_URL=
```

## Production Safety Checklist

Before deployment:

- `DJANGO_DEBUG=False`
- Real `DJANGO_SECRET_KEY` is set.
- `DJANGO_ALLOWED_HOSTS` includes the backend domain.
- `CORS_ALLOWED_ORIGINS` includes the frontend domain.
- `CSRF_TRUSTED_ORIGINS` includes the frontend domain.
- Real database URL is set.
- Real email SMTP variables are set.
- Real Flutterwave production keys are set only in production.
- No real `.env` file is committed.
