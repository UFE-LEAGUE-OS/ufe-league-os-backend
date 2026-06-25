# 06. Frontend Integration Guide

This guide is for the React/Vite frontend team.

## Base URL

Local backend:

```ts
const API_BASE_URL = "http://localhost:8000";
```

Staging backend:

```ts
const API_BASE_URL = "https://ufe-league-os-backend.onrender.com";
```

Recommended environment variable:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Authentication

After login, store the access token and send it on protected requests:

```ts
headers: {
  Authorization: `Bearer ${accessToken}`,
}
```

The backend uses JWT. Most protected endpoints will return `401` when the token is missing or expired.

## Registration and OTP Flow

Recommended frontend flow:

```text
Register
   |
   v
Show OTP screen
   |
   v
Verify OTP
   |
   v
Login or continue authenticated session
   |
   v
Route user by role/dashboard
```

Important endpoints:

```text
POST /api/accounts/register/
POST /api/accounts/verify-otp/
POST /api/accounts/resend-otp/
POST /api/accounts/login/
GET  /api/accounts/me/
GET  /api/dashboards/me/
```

## Role Dashboard Routing

Backend dashboard endpoints:

| Role | Endpoint |
|---|---|
| Fan | `/api/dashboards/fan/` |
| Club Admin | `/api/dashboards/club-admin/` |
| League Admin | `/api/dashboards/league-admin/` |
| Union Admin | `/api/dashboards/union-admin/` |
| Super Admin | `/api/dashboards/super-admin/` |
| Referee | `/api/dashboards/referee/` |
| Ticketing Officer | `/api/dashboards/ticketing-officer/` |
| Sponsor | `/api/dashboards/sponsor/` |

Frontend route paths can be different, but the API client must call these backend paths.

## Public Browse Pages

These do not require authentication:

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

Use these for landing page, public browse, club directory, league detail, match detail, and standings pages.

## Profile and Preferences

Use these backend paths:

```text
GET/PATCH /api/accounts/profile/
GET/PATCH /api/accounts/notifications/
GET/PATCH /api/accounts/interests/
```

Do not call these root paths unless backend aliases are later added:

```text
/api/profile/
/api/notifications/
```

## FAN-004 Ticket Purchase Flow

### 1. List ticket types for match

```http
GET /api/ticketing/matches/{matchId}/ticket-types/
```

No auth required.

### 2. Initialize checkout

```http
POST /api/ticketing/orders/flutterwave/initialize/
Authorization: Bearer <access_token>
Content-Type: application/json
```

Body:

```json
{
  "ticket_type_id": 1,
  "quantity": 2
}
```

Response includes:

```json
{
  "tx_ref": "LOS-TICKET-...",
  "checkout_url": "https://checkout.flutterwave.com/..."
}
```

### 3. Redirect user to Flutterwave

Frontend should redirect the browser to `checkout_url`.

### 4. Flutterwave redirects back

Flutterwave redirects to:

```text
/api/ticketing/flutterwave/verify/?tx_ref=...
```

The backend verifies the transaction and issues tickets if valid.

A later frontend improvement can use a frontend success route, but backend verification must remain the source of truth.

### 5. Get user's tickets

```http
GET /api/ticketing/tickets/me/
Authorization: Bearer <access_token>
```

### 6. Ticket validation/check-in

Ticketing officer scans a ticket code and sends:

```http
POST /api/ticketing/validate/
Authorization: Bearer <ticketing_officer_access_token>
Content-Type: application/json
```

Body:

```json
{
  "scanned_code": "ticket-uuid-value",
  "match_id": 1
}
```

## Sponsorship Flutterwave Flow

Sponsorship checkout endpoint:

```text
POST /api/sponsorships/agreements/<agreement_id>/flutterwave/initialize/
```

Verify endpoint:

```text
GET /api/sponsorships/flutterwave/verify/
```

Do not mix sponsorship redirect URLs with ticketing redirect URLs.

## Error Handling Expectations

| Status | Meaning | Frontend Action |
|---|---|---|
| `400` | Bad request or validation error | Show field/API error. |
| `401` | Not authenticated | Redirect to login or refresh token. |
| `403` | Authenticated but not allowed | Show permission message. |
| `404` | Resource not found | Show not-found/empty state. |
| `502` | External service problem | Show retry/payment service message. |

## Frontend QA Checklist

Before merging frontend integration:

- Register/login flow works locally and staging.
- OTP flow uses the correct backend endpoints.
- Dashboard API path matches user role.
- Public browse pages do not require tokens.
- Authenticated pages include Bearer token.
- Ticket checkout returns a Flutterwave checkout URL.
- Fan tickets page uses `/api/ticketing/tickets/me/`.
- Ticket validation uses a ticketing officer/admin token.
- Frontend does not assume a ticket is issued before backend verification.
