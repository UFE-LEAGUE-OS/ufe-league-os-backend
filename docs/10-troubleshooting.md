# 10. Troubleshooting Guide

## Backend Container Is Not Running

Check containers:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs backend --tail=200
```

Run backend in foreground for clearer errors:

```bash
docker compose up backend
```

## `service "backend" is not running`

The backend container exited. Get the logs:

```bash
docker compose logs backend --tail=200
```

Fix the first traceback, then restart:

```bash
docker compose up -d
```

## `ModuleNotFoundError`

Example:

```text
ModuleNotFoundError: No module named 'google'
```

Fix:

1. Add package to `backend/requirements.txt`.
2. Rebuild image.

```bash
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

## Django Template Watcher Error

Example:

```text
OSError: [Errno 5] Input/output error: '/app/templates'
```

Fix:

- Keep templates inside installed app template directories.
- Example path:

```text
backend/dashboards/templates/api_landing.html
```

- Keep settings:

```python
"DIRS": []
```

## Pending Migrations

Check:

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run
```

If changes are detected:

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

Commit the migration file.

## Black Fails

Example:

```text
would reformat ...
```

Fix:

```bash
docker compose exec backend black .
docker compose exec backend black --check .
```

## Ruff Fails

Fix automatically where possible:

```bash
docker compose exec backend ruff check . --fix
docker compose exec backend ruff check .
```

## Tests Fail

Run only the failing app first:

```bash
docker compose exec backend python manage.py test ticketing
```

Then run the full suite:

```bash
docker compose exec backend python manage.py test
```

## Swagger Shows Serializer Warnings

Warnings like:

```text
unable to guess serializer
```

come from drf-spectacular when a function-based view does not expose a clear serializer for schema generation.

They do not always break the backend, but should be improved later by adding `@extend_schema` or converting views to generic views.

## Frontend Gets 404 for Profile or Notifications

Backend has:

```text
/api/accounts/profile/
/api/accounts/notifications/
```

If frontend calls:

```text
/api/profile/
/api/notifications/
```

it will get `404`.

Fix either:

1. Frontend updates API paths, or
2. Backend adds temporary alias routes.

## CORS Error in Browser

Check backend `.env`:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173
```

For staging:

```env
CORS_ALLOWED_ORIGINS=https://ufe-league-os-frontend.onrender.com
CSRF_TRUSTED_ORIGINS=https://ufe-league-os-frontend.onrender.com
```

Restart backend after env changes.

## OTP Email Not Received

Local testing:

```env
SEND_OTP_EMAILS=False
PRINT_DEV_OTPS=True
```

Then read OTP from logs:

```bash
docker compose logs backend --tail=200
```

Staging with Brevo:

```env
SEND_OTP_EMAILS=True
PRINT_DEV_OTPS=False
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=2525
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

## Flutterwave Checkout Fails

Check:

```env
FLUTTERWAVE_SECRET_KEY=
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3
FLUTTERWAVE_REDIRECT_URL=
FLUTTERWAVE_TICKET_REDIRECT_URL=
```

Also check backend logs for `FlutterwaveError`.

## Git CRLF Warnings on Windows

Example:

```text
CRLF will be replaced by LF the next time Git touches it
```

This is usually okay. The project has line-ending normalization. Continue unless tests/lint fail.

## Safe Final Verification Before Push

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
git status
```
