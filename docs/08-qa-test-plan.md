# 08. QA Test Plan

This guide is for QA testers and developers validating backend behavior.

## General QA Rules

- Test locally first.
- Test staging after CI passes.
- Use test users and Flutterwave test credentials only.
- Do not use real production payment keys in local or staging tests.
- Capture request body, response body, status code, and user role for each bug report.

## Standard Backend Test Command

```bash
docker compose exec backend python manage.py test
```

Focused tests:

```bash
docker compose exec backend python manage.py test accounts
docker compose exec backend python manage.py test dashboards
docker compose exec backend python manage.py test governance
docker compose exec backend python manage.py test sponsorships
docker compose exec backend python manage.py test ticketing
```

## Pre-QA Technical Checks

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
```

## Authentication QA

### Register

Endpoint:

```text
POST /api/accounts/register/
```

Check:

- Valid user can register.
- Duplicate email is rejected.
- Weak password is rejected.
- OTP requirement is returned.
- User starts with expected role.
- User is not email-verified until OTP verification.

### OTP

Endpoints:

```text
POST /api/accounts/verify-otp/
POST /api/accounts/resend-otp/
```

Check:

- Correct OTP verifies user.
- Wrong OTP fails.
- Expired OTP fails.
- Resend creates a usable OTP.
- Local OTP appears in backend logs when `PRINT_DEV_OTPS=True`.

### Login

Endpoint:

```text
POST /api/accounts/login/
```

Check:

- Login works with email/password.
- Login works with phone if supported by serializer.
- Incorrect password fails.
- Response includes access/refresh tokens.
- `/api/accounts/me/` works with Bearer token.

## Dashboard QA

Check each role can access its own dashboard:

```text
GET /api/dashboards/fan/
GET /api/dashboards/club-admin/
GET /api/dashboards/league-admin/
GET /api/dashboards/union-admin/
GET /api/dashboards/super-admin/
GET /api/dashboards/referee/
GET /api/dashboards/ticketing-officer/
GET /api/dashboards/sponsor/
```

Check:

- Correct role receives `200`.
- Wrong role receives permission error.
- Anonymous user receives `401`.

## Public Browse QA

No token should be required:

```text
GET /api/dashboards/public/fixtures/
GET /api/dashboards/public/results/
GET /api/dashboards/public/standings/
GET /api/dashboards/public/clubs/
GET /api/dashboards/public/unions/
GET /api/dashboards/public/leagues/
GET /api/dashboards/public/competitions/
GET /api/dashboards/public/matches/<match_id>/
```

Check:

- Anonymous request returns `200`.
- Empty database returns safe empty lists, not server errors.
- Invalid `match_id` returns `404`.

## Sponsorship QA

Core flow:

1. Register sponsor account.
2. Create/list sponsor packages.
3. Create sponsor agreement.
4. Approve/activate agreement.
5. Initialize Flutterwave checkout.
6. Verify payment.
7. Confirm payment and revenue distribution behavior.

Important endpoints:

```text
POST /api/sponsorships/register/
GET/POST /api/sponsorships/accounts/
GET/POST /api/sponsorships/packages/
GET/POST /api/sponsorships/agreements/
POST /api/sponsorships/agreements/<agreement_id>/flutterwave/initialize/
GET /api/sponsorships/flutterwave/verify/
POST /api/sponsorships/flutterwave/webhook/
```

Check:

- Unauthorized users cannot manage sponsor records they should not access.
- Flutterwave checkout returns URL in test mode.
- Failed payment does not mark payment successful.
- Webhook uses secret hash where configured.

## FAN-004 Ticketing QA

### Test Case 1: Public ticket type listing

```text
GET /api/ticketing/matches/<match_id>/ticket-types/
```

Expected:

- `200`
- Response contains match info.
- Response contains ticket types.
- Active ticket types are visible.

### Test Case 2: Anonymous checkout rejected

```text
POST /api/ticketing/orders/flutterwave/initialize/
```

Expected:

- `401`

### Test Case 3: Fan initializes checkout

Authenticated fan sends:

```json
{
  "ticket_type_id": 1,
  "quantity": 2
}
```

Expected:

- `201`
- Response contains `tx_ref`.
- Response contains `checkout_url`.
- Order status is `PENDING`.
- No tickets are issued yet.

### Test Case 4: Quantity exceeds stock

Request more tickets than available.

Expected:

- `400`
- Error mentions quantity/stock.

### Test Case 5: Successful payment verification

```text
GET /api/ticketing/flutterwave/verify/?tx_ref=<tx_ref>
```

Expected:

- `200`
- Order status becomes `PAID`.
- Tickets are created.
- `quantity_sold` increases.
- Ticket records have active status.

### Test Case 6: Duplicate verification

Call verification twice with the same `tx_ref`.

Expected:

- No duplicate tickets are created.
- Second call returns safe success or existing ticket state.

### Test Case 7: Failed payment verification

Mock/test a failed transaction.

Expected:

- Order becomes `FAILED` or `CANCELLED`.
- No tickets are created.

### Test Case 8: Fan views own tickets

```text
GET /api/ticketing/tickets/me/
```

Expected:

- `200`
- Fan sees only their own tickets.
- Fan cannot see another fan's tickets.

### Test Case 9: Ticketing officer validates ticket

```text
POST /api/ticketing/validate/
```

Body:

```json
{
  "scanned_code": "ticket-uuid-value",
  "match_id": 1
}
```

Expected:

- First scan returns `VALID`.
- Ticket status becomes `USED`.
- `checked_in_by` is saved.
- Validation log is created.

### Test Case 10: Already used ticket

Scan same ticket again.

Expected:

- `400`
- Result is `ALREADY_USED`.

### Test Case 11: Normal fan cannot validate

Expected:

- `403`

## Bug Report Template

```md
## Bug Summary

## Environment
- Local / Staging:
- Backend branch:
- Frontend branch:
- User role:

## Endpoint
METHOD /path/

## Request Body

## Expected Result

## Actual Result

## Screenshots / Logs

## Reproduction Steps
1.
2.
3.
```
