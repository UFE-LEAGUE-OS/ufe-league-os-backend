# FAN-004 Ticketing Test Mode README

## League OS Backend - Match Ticket Purchase + Flutterwave Test Mode Guide

This document explains how to test the **FAN-004 Match Ticket Purchase** backend flow while Flutterwave is still in **test mode**.

It is written for:

- Backend developers
- Frontend developers
- QA testers
- DevOps users
- Project reviewers
- Future maintainers

---

## 1. Purpose of FAN-004

FAN-004 allows a fan to buy a match ticket through League OS.

The backend supports:

1. Listing ticket types for a match.
2. Creating a pending ticket order.
3. Initializing Flutterwave checkout.
4. Redirecting the fan to Flutterwave for payment.
5. Verifying the payment on the backend.
6. Issuing tickets only after successful backend verification.
7. Allowing the fan to view purchased tickets.
8. Allowing a ticketing officer to validate/check in the ticket.

---

## 2. Important Backend Rule

Tickets must never be issued just because the frontend says payment was successful.

Correct rule:

```text
Only issue tickets after the backend verifies the payment with Flutterwave.
```

Correct flow:

```text
Fan selects ticket type
Backend creates pending ticket order
Backend initializes Flutterwave checkout
Flutterwave returns checkout URL
Fan pays on Flutterwave
Flutterwave redirects back to backend
Backend verifies transaction with Flutterwave
Backend marks order as PAID
Backend issues ticket
Fan sees ticket
Ticketing officer validates ticket
```

---

## 3. Current FAN-004 Backend Status

The current backend implementation includes:

- `TicketType`
- `TicketOrder`
- `TicketOrderItem`
- `Ticket`
- `TicketValidationLog`
- Public ticket type listing
- Fan checkout initialization
- Flutterwave checkout integration
- Flutterwave payment verification
- Flutterwave webhook endpoint
- Fan order listing
- Fan ticket listing
- Ticket validation/check-in
- Ticketing tests

Local implementation status from the completed FAN-004 work:

```text
Ticketing tests: 14 passed
Full backend tests: 142 passed
Django checks: passed
Black: passed
Ruff: passed
Migrations: no pending changes
```

Recommended local confirmation commands:

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py test ticketing
docker compose exec backend python manage.py check
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
```

---

## 4. Local Environment Variables

Each developer or QA tester must use their own Flutterwave test mode credentials.

Do **not** commit real keys to Git.

Add these values to your local `.env` file:

```env
FLUTTERWAVE_MODE=test
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3

FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your-test-public-key
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your-test-secret-key
FLUTTERWAVE_SECRET_HASH=league-os-local-test-webhook-secret

FLUTTERWAVE_TICKET_REDIRECT_URL=http://localhost:8000/api/ticketing/flutterwave/verify/
FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment

FLUTTERWAVE_PAYMENT_LOGO_URL=
FLUTTERWAVE_TIMEOUT_SECONDS=30
```

For staging on Render, use the staging backend URL:

```env
FLUTTERWAVE_TICKET_REDIRECT_URL=https://ufe-league-os-backend.onrender.com/api/ticketing/flutterwave/verify/
```

---

## 5. Where to Get Flutterwave Test Keys

Flutterwave API keys are account-specific. There are no universal public test API credentials that should be shared in the repository.

Use this approach:

1. Log in to the Flutterwave dashboard.
2. Switch the dashboard to **Test Mode**.
3. Go to the API keys/settings area.
4. Copy the test public key.
5. Copy the test secret key.
6. Add them to your local `.env` file.
7. Restart the backend container.

Example key formats:

```text
FLWPUBK_TEST-xxxxxxxxxxxxxxxxxxxxx-X
FLWSECK_TEST-xxxxxxxxxxxxxxxxxxxxx-X
```

Never commit this:

```text
FLWSECK_TEST-xxxxxxxxxxxxxxxxxxxxx-X
```

The secret key belongs only in `.env`, Render environment variables, or another secure secret manager.

Official reference:

- Flutterwave Authentication: https://developer.flutterwave.com/docs/authentication

---

## 6. Flutterwave Test Mode Payment Details

### 6.1 What can be safely documented

Flutterwave's official testing documentation currently describes sandbox testing through the `X-Scenario-Key` header.

The documented format for card scenarios is:

```text
X-Scenario-Key: scenario:<scenario_value>&issuer:<issuer_value>
```

Useful official scenario examples include:

```text
Successful PIN flow:
X-Scenario-Key: scenario:auth_pin&issuer:approved

Successful 3DS flow:
X-Scenario-Key: scenario:auth_3ds&issuer:approved

Incorrect PIN:
X-Scenario-Key: scenario:auth_pin&issuer:incorrect_pin

Insufficient funds:
X-Scenario-Key: scenario:auth_avs&issuer:insufficient_funds
```

Flutterwave also documents mobile money testing scenarios such as:

```text
Default mobile money sandbox flow:
No X-Scenario-Key header required

Redirect mobile money flow:
X-Scenario-Key: scenario:auth_redirect
```

Official reference:

- Flutterwave Testing: https://developer.flutterwave.com/docs/testing

### 6.2 Important note about hosted checkout card numbers

For hosted checkout testing, do **not** hardcode card details into League OS documentation as if they are permanent production-like credentials.

Use one of these safer options:

1. Use the test card or payment instructions shown in your Flutterwave dashboard or payment modal.
2. Use Flutterwave's current official testing documentation.
3. Ask the QA lead or Flutterwave account owner to confirm the current sandbox card/payment details before sign-off.

Payment providers can update sandbox cards, PINs, OTPs, and test helpers. Keep the README current if Flutterwave changes its test instructions.

---

## 7. Restart Backend After Adding Keys

After adding Flutterwave test keys to `.env`, restart Docker:

```bash
docker compose down
docker compose up -d
docker compose ps
```

Confirm the backend is running:

```bash
docker compose logs backend --tail=80
```

Expected result:

```text
System check identified no issues
Starting development server at http://0.0.0.0:8000/
```

---

## 8. Required Test Data

To test ticket purchase, the backend needs:

1. A fan user.
2. A scheduled match.
3. At least one active ticket type for that match.
4. Ticket stock greater than zero.
5. Flutterwave test credentials in `.env`.

Example test data:

```text
Fan:
fan@example.com

Match:
KOBS Rugby Club vs Heathens Rugby Club

Venue:
Legends Rugby Grounds

Ticket Type:
Ordinary

Price:
UGX 10,000

Quantity Available:
100

Status:
ACTIVE
```

---

## 9. Main FAN-004 API Endpoints

```text
GET  /api/ticketing/matches/{match_id}/ticket-types/
GET  /api/ticketing/orders/
POST /api/ticketing/orders/flutterwave/initialize/
GET  /api/ticketing/tickets/me/
GET  /api/ticketing/flutterwave/verify/
POST /api/ticketing/flutterwave/webhook/
POST /api/ticketing/validate/
```

---

## 10. Step-by-Step QA Flow

### Step 1: Start backend

```bash
docker compose up -d
docker compose ps
```

### Step 2: Open Swagger

```text
http://localhost:8000/api/docs/
```

### Step 3: Log in as a fan

Use the login endpoint and copy the access token.

The frontend or Swagger should send:

```text
Authorization: Bearer <fan_access_token>
```

### Step 4: List ticket types for a match

```http
GET /api/ticketing/matches/{match_id}/ticket-types/
```

Expected response:

```json
{
  "match": {
    "id": 1,
    "label": "KOBS Rugby Club vs Heathens Rugby Club",
    "venue": "Legends Rugby Grounds",
    "status": "SCHEDULED"
  },
  "count": 1,
  "ticket_types": [
    {
      "id": 1,
      "name": "Ordinary",
      "price": "10000.00",
      "currency": "UGX",
      "quantity_available": 100,
      "quantity_sold": 0,
      "remaining_quantity": 100,
      "status": "ACTIVE"
    }
  ]
}
```

QA checks:

- The endpoint works without login.
- Only active ticket types show by default.
- `remaining_quantity` is correct.
- Ticket type belongs to the correct match.

---

### Step 5: Initialize Flutterwave checkout

```http
POST /api/ticketing/orders/flutterwave/initialize/
Authorization: Bearer <fan_access_token>
Content-Type: application/json
```

Request body:

```json
{
  "ticket_type_id": 1,
  "quantity": 2
}
```

Expected response:

```json
{
  "message": "Flutterwave ticket checkout initialized successfully.",
  "order": {
    "id": 1,
    "total_amount": "20000.00",
    "currency": "UGX",
    "status": "PENDING",
    "provider": "FLUTTERWAVE"
  },
  "tx_ref": "LOS-TICKET-1-xxxxxxxxxxxxxxxx",
  "checkout_url": "https://checkout.flutterwave.com/..."
}
```

QA checks:

- User must be authenticated.
- Order starts as `PENDING`.
- Ticket is not issued yet.
- `checkout_url` is returned.
- `tx_ref` is unique.
- Total amount equals price multiplied by quantity.

---

### Step 6: Complete Flutterwave test payment

Open the returned `checkout_url` in a browser.

Use Flutterwave test mode payment details from the Flutterwave dashboard or current Flutterwave testing documentation.

QA checks:

- Do not use a real bank card.
- Make sure Flutterwave dashboard is in test mode.
- Make sure backend `.env` uses test keys.
- Make sure the redirect URL points back to the backend verification endpoint.

---

### Step 7: Verify payment

Flutterwave redirects to:

```http
GET /api/ticketing/flutterwave/verify/?tx_ref=<tx_ref>
```

You can also test manually:

```text
http://localhost:8000/api/ticketing/flutterwave/verify/?tx_ref=LOS-TICKET-1-xxxxxxxxxxxxxxxx
```

Expected success response:

```json
{
  "message": "Flutterwave ticket payment verified successfully.",
  "order": {
    "id": 1,
    "status": "PAID",
    "provider": "FLUTTERWAVE"
  },
  "tickets": [
    {
      "ticket_code": "uuid-ticket-code",
      "qr_payload": "uuid-ticket-code",
      "status": "ACTIVE"
    }
  ]
}
```

QA checks:

- Order changes from `PENDING` to `PAID`.
- Ticket is issued only after verification.
- Ticket status is `ACTIVE`.
- `quantity_sold` increases.
- The number of issued tickets equals the quantity purchased.

---

### Step 8: Confirm duplicate verification does not issue duplicate tickets

Call the same verify endpoint again:

```http
GET /api/ticketing/flutterwave/verify/?tx_ref=<same_tx_ref>
```

Expected behavior:

- Response should still be successful.
- No duplicate tickets should be created.
- Ticket count for the order should remain the same.

This is called idempotency.

Payment redirects and webhooks can happen more than once, so the backend must not issue duplicate tickets.

---

### Step 9: View fan tickets

```http
GET /api/ticketing/tickets/me/
Authorization: Bearer <fan_access_token>
```

Expected response:

```json
{
  "count": 1,
  "tickets": [
    {
      "ticket_code": "uuid-ticket-code",
      "status": "ACTIVE",
      "qr_payload": "uuid-ticket-code"
    }
  ]
}
```

QA checks:

- Fan sees only their own tickets.
- Fan does not see another user's tickets.
- Ticket has a QR-ready payload.

---

### Step 10: Validate/check in ticket

Log in as a ticketing officer or admin.

```http
POST /api/ticketing/validate/
Authorization: Bearer <ticketing_officer_access_token>
Content-Type: application/json
```

Request body:

```json
{
  "scanned_code": "uuid-ticket-code",
  "match_id": 1
}
```

Expected success response:

```json
{
  "result": "VALID",
  "message": "Ticket is valid and has been checked in."
}
```

QA checks:

- Ticket changes from `ACTIVE` to `USED`.
- `used_at` is set.
- `checked_in_by` is set.
- Validation log is created.

---

### Step 11: Scan the same ticket again

Use the same request body again:

```json
{
  "scanned_code": "uuid-ticket-code",
  "match_id": 1
}
```

Expected response:

```json
{
  "result": "ALREADY_USED",
  "message": "Ticket has already been used."
}
```

QA checks:

- Already-used ticket is rejected.
- Another validation log is created.
- Ticket remains `USED`.

---

## 11. Negative QA Tests

QA should also test these failure cases:

### Anonymous user tries to initialize checkout

Expected result:

```text
401 Unauthorized
```

### Fan tries to validate ticket

Expected result:

```text
403 Forbidden
```

### Quantity is higher than available stock

Request:

```json
{
  "ticket_type_id": 1,
  "quantity": 999999
}
```

Expected result:

```text
400 Bad Request
```

### Wrong transaction reference

```http
GET /api/ticketing/flutterwave/verify/?tx_ref=wrong-reference
```

Expected result:

```text
404 Ticket order not found
```

### Wrong match during ticket validation

Use a valid ticket code but wrong `match_id`.

Expected result:

```text
WRONG_MATCH
```

### Already-used ticket

Scan the same ticket twice.

Expected result:

```text
ALREADY_USED
```

---

## 12. Frontend Integration Notes

The frontend should follow this flow:

1. Load ticket types:

```text
GET /api/ticketing/matches/{match_id}/ticket-types/
```

2. Fan selects ticket type and quantity.

3. Frontend calls:

```text
POST /api/ticketing/orders/flutterwave/initialize/
```

4. Backend returns:

```json
{
  "checkout_url": "https://checkout.flutterwave.com/...",
  "tx_ref": "LOS-TICKET-..."
}
```

5. Frontend redirects browser to `checkout_url`.

6. After Flutterwave payment, the user returns through the backend verify URL.

7. Frontend should show success only after backend confirms `order.status` is `PAID`.

8. Frontend should then fetch:

```text
GET /api/ticketing/tickets/me/
```

Important frontend rule:

```text
Do not display a final issued ticket until backend verification confirms payment and returns the ticket.
```

---

## 13. Backend Developer Notes

The core backend files for FAN-004 are:

```text
backend/ticketing/models.py
backend/ticketing/admin.py
backend/ticketing/serializers.py
backend/ticketing/views.py
backend/ticketing/urls.py
backend/ticketing/services/orders.py
backend/ticketing/services/flutterwave_gateway.py
backend/ticketing/tests.py
```

Important implementation rules:

- Keep payment logic in services.
- Keep views thin.
- Do not call real Flutterwave inside unit tests.
- Mock Flutterwave responses in tests.
- Use transactions around ticket issuing.
- Re-check stock before issuing tickets.
- Do not issue duplicate tickets for the same paid order.
- Keep Flutterwave secret keys out of Git.

---

## 14. DevOps Staging Notes

For Render staging, add these environment variables:

```env
FLUTTERWAVE_MODE=test
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your-staging-test-public-key
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your-staging-test-secret-key
FLUTTERWAVE_SECRET_HASH=your-staging-webhook-secret
FLUTTERWAVE_TICKET_REDIRECT_URL=https://ufe-league-os-backend.onrender.com/api/ticketing/flutterwave/verify/
FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment
FLUTTERWAVE_PAYMENT_LOGO_URL=
FLUTTERWAVE_TIMEOUT_SECONDS=30
```

After updating Render variables:

1. Redeploy backend.
2. Run migrations.
3. Confirm `/api/health/`.
4. Confirm `/api/docs/`.
5. Test ticket checkout in Flutterwave test mode.

---

## 15. Local Developer Commands

Start backend:

```bash
docker compose up -d
```

Check containers:

```bash
docker compose ps
```

Run backend checks:

```bash
docker compose exec backend python manage.py check
```

Run migrations:

```bash
docker compose exec backend python manage.py migrate
```

Check pending migrations:

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run
```

Run ticketing tests:

```bash
docker compose exec backend python manage.py test ticketing
```

Run full tests:

```bash
docker compose exec backend python manage.py test
```

Run formatting checks:

```bash
docker compose exec backend black --check .
docker compose exec backend ruff check .
```

Fix formatting:

```bash
docker compose exec backend black .
docker compose exec backend ruff check . --fix
```

---

## 16. QA Sign-Off Checklist

### Happy path

- [ ] Fan can list ticket types.
- [ ] Fan can initialize Flutterwave checkout.
- [ ] Backend creates pending order.
- [ ] Flutterwave checkout URL is returned.
- [ ] Fan can complete payment in test mode.
- [ ] Backend verifies Flutterwave payment.
- [ ] Order becomes `PAID`.
- [ ] Ticket is issued.
- [ ] Fan can view issued ticket.
- [ ] Ticketing officer can validate ticket.
- [ ] Ticket cannot be validated twice.

### Negative path

- [ ] Anonymous user cannot initialize checkout.
- [ ] Fan cannot validate tickets.
- [ ] Checkout rejects quantity above available stock.
- [ ] Failed payment does not issue tickets.
- [ ] Wrong `tx_ref` is rejected.
- [ ] Wrong match validation is rejected.
- [ ] Already-used ticket is rejected.

### Security checks

- [ ] No real Flutterwave keys committed.
- [ ] No real card details used.
- [ ] Secret key exists only in `.env` or Render environment variables.
- [ ] Frontend never receives Flutterwave secret key.
- [ ] Ticket is issued only after backend verification.

---

## 17. Recommended Follow-Up Improvement

The current FAN-004 implementation checks stock:

1. Before checkout initialization.
2. Again before ticket issuing after payment verification.

This prevents tickets from being issued when stock is gone, but it does not fully reserve stock during the payment window.

Recommended future card:

```text
FAN-004 Improvement: Add ticket reservation expiry
```

Suggested behavior:

```text
Fan starts checkout
Backend reserves ticket stock for 10 minutes
If payment succeeds in time, issue ticket
If payment is not completed in time, release reservation
```

This is recommended before production ticket sales, but it is not a blocker for the current FAN-004 backend completion.

---

## 18. Add This Document to the Codebase

Recommended path:

```text
docs/FAN-004-ticketing-test-mode-readme.md
```

Recommended branch:

```bash
git switch develop
git pull origin develop
git switch -c docs/fan-004-ticketing-test-guide
```

Commit commands:

```bash
git status
git add docs/FAN-004-ticketing-test-mode-readme.md
git commit -m "Document FAN-004 ticketing test mode README"
git push -u origin docs/fan-004-ticketing-test-guide
```

Manual PR details:

```text
Base: develop
Compare: docs/fan-004-ticketing-test-guide
Title: Document FAN-004 ticketing test mode README
```

PR description:

```md
## Summary

This PR adds a single README-style test guide for FAN-004 ticketing.

It covers:
- Flutterwave test mode setup
- Safe handling of test API keys
- Test payment scenario guidance
- Ticket purchase API flow
- Ticket verification flow
- Ticket validation/check-in flow
- Frontend integration notes
- DevOps staging variables
- QA sign-off checklist
- Recommended ticket reservation expiry follow-up



