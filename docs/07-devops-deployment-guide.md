# 07. DevOps and Deployment Guide

This guide is for deployment, CI/CD, environment setup, and production support.

## Runtime Services

The backend requires:

| Service | Purpose |
|---|---|
| Django/Gunicorn | Application server. |
| PostgreSQL | Main relational database. |
| Static/media storage | User uploads, avatars, future media. |
| SMTP provider | OTP and transactional email. |
| Flutterwave | Sponsorship and ticket payment checkout. |

Local Docker Compose runs:

```text
backend
db
```

## Local Docker Compose

```bash
docker compose up -d --build
docker compose ps
```

Backend local port:

```text
http://localhost:8000
```

Database local port:

```text
localhost:5432
```

## Dockerfile Behavior

The Dockerfile:

1. Uses Python 3.12 slim.
2. Installs system dependencies.
3. Installs `backend/requirements.txt`.
4. Copies `backend/` into `/app`.
5. Exposes port `8000`.
6. Runs migrations, collectstatic, and Gunicorn by default.

The Docker Compose override for local development uses:

```text
python manage.py migrate && python manage.py runserver 0.0.0.0:8000
```

## Render/Staging Deployment Notes

Recommended Render settings:

| Setting | Value |
|---|---|
| Build command | `pip install -r backend/requirements.txt` or Docker build depending on service type |
| Start command | `python backend/manage.py migrate && gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT` |
| Python version | 3.12 |
| Database | PostgreSQL / external DB |
| Environment | Use Render dashboard, not committed `.env` |

If using the Dockerfile, ensure Render builds from repo root and uses the Dockerfile.

## Required Staging Environment Variables

Core:

```env
DJANGO_SECRET_KEY=<secure-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=ufe-league-os-backend.onrender.com
DATABASE_URL=<postgres-url>
```

Frontend access:

```env
CORS_ALLOWED_ORIGINS=https://ufe-league-os-frontend.onrender.com
CSRF_TRUSTED_ORIGINS=https://ufe-league-os-frontend.onrender.com
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Email:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SEND_OTP_EMAILS=True
PRINT_DEV_OTPS=False
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=2525
EMAIL_HOST_USER=<brevo-login>
EMAIL_HOST_PASSWORD=<brevo-key>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=League OS <verified-sender@example.com>
SERVER_EMAIL=League OS <verified-sender@example.com>
```

Flutterwave test/staging:

```env
FLUTTERWAVE_MODE=test
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3
FLUTTERWAVE_PUBLIC_KEY=<test-public-key>
FLUTTERWAVE_SECRET_KEY=<test-secret-key>
FLUTTERWAVE_SECRET_HASH=<webhook-secret>
FLUTTERWAVE_REDIRECT_URL=https://ufe-league-os-backend.onrender.com/api/sponsorships/flutterwave/verify/
FLUTTERWAVE_TICKET_REDIRECT_URL=https://ufe-league-os-backend.onrender.com/api/ticketing/flutterwave/verify/
FLUTTERWAVE_PAYMENT_TITLE=League OS Sponsorship Payment
FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment
FLUTTERWAVE_TIMEOUT_SECONDS=30
```

## Health Checks

Use:

```text
GET /api/health/
```

Expected:

```json
{
  "status": "OK",
  "service": "League OS Backend API",
  "version": "sprint-1-foundation"
}
```

## CI/CD Quality Gate

Before deployment, these should pass:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
black --check .
ruff check .
python manage.py test
```

In Docker local:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
```

## Deployment Verification Checklist

After deployment:

1. Open `/api/health/`.
2. Open `/api/docs/`.
3. Test frontend CORS by loading staging frontend.
4. Register a user.
5. Verify OTP email is received.
6. Login and call `/api/accounts/me/`.
7. Confirm public clubs/fixtures endpoints return data.
8. Confirm Flutterwave initialization returns a checkout URL in test mode.
9. Confirm no secrets are visible in logs.
10. Confirm migrations are applied.

## Log Troubleshooting

### Container crashes immediately

Check logs:

```bash
docker compose logs backend --tail=200
```

### Missing dependency

Add to `backend/requirements.txt`, rebuild image:

```bash
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

### CORS issue

Check:

```env
CORS_ALLOWED_ORIGINS=
CSRF_TRUSTED_ORIGINS=
```

### OTP email not sending

Check:

```env
SEND_OTP_EMAILS=True
PRINT_DEV_OTPS=False
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=2525
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

### Flutterwave checkout fails

Check:

```env
FLUTTERWAVE_SECRET_KEY=
FLUTTERWAVE_BASE_URL=
FLUTTERWAVE_REDIRECT_URL=
FLUTTERWAVE_TICKET_REDIRECT_URL=
```

Also inspect backend logs for a `FlutterwaveError`.
