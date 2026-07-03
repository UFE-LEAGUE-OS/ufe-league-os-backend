# 05. API Reference

Base URL locally:

```text
http://localhost:8000
```

Staging backend:

```text
https://ufe-league-os-backend.onrender.com
```

Swagger/OpenAPI:

```text
GET /api/docs/
GET /api/schema/
```

## Authentication Header

For protected endpoints:

```http
Authorization: Bearer <access_token>
```

## Root and Health

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | No | Visual backend landing page. |
| `GET` | `/api/` | No | JSON API discovery payload. |
| `GET` | `/api/health/` | No | Health check. |
| `GET` | `/api/docs/` | No | Swagger UI. |
| `GET` | `/api/schema/` | No | OpenAPI schema. |

## Accounts

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/accounts/roles/` | No | List supported user roles. |
| `POST` | `/api/accounts/register/` | No | Register a new user. |
| `POST` | `/api/accounts/login/` | No | Login with email/phone and password. |
| `POST` | `/api/accounts/google/` | No | Google authentication. |
| `GET` | `/api/accounts/me/` | Yes | Current authenticated user. |
| `POST` | `/api/accounts/verify-otp/` | No | Verify email OTP. |
| `POST` | `/api/accounts/resend-otp/` | No | Resend OTP. |
| `POST` | `/api/accounts/password-reset/request/` | No | Request password reset. |
| `POST` | `/api/accounts/password-reset/confirm/` | No | Confirm password reset. |
| `GET/PATCH` | `/api/accounts/profile/` | Yes | Get/update authenticated profile. |
| `DELETE` | `/api/accounts/profile/avatar/` | Yes | Remove profile avatar. |
| `POST` | `/api/accounts/become-sponsor/` | Yes | Convert/request sponsor role flow. |
| `POST` | `/api/accounts/superadmin/create-user/` | Yes | Super admin user creation. |
| `POST` | `/api/accounts/union-admin/create-user/` | Yes | Union admin user creation. |
| `POST` | `/api/accounts/league-admin/create-user/` | Yes | League admin user creation. |
| `POST` | `/api/accounts/club-admin/create-user/` | Yes | Club admin user creation. |
| `POST` | `/api/accounts/follow/` | Yes | Follow/unfollow content. |
| `GET` | `/api/accounts/follow/check/<content_type>/<object_id>/` | Yes | Check follow state. |
| `GET/PATCH` | `/api/accounts/notifications/` | Yes | Notification preferences. |
| `GET/PATCH` | `/api/accounts/interests/` | Yes | Interest preferences. |
| `GET` | `/api/accounts/wallet/` | Yes | Wallet info. |
| `GET` | `/api/accounts/payments/` | Yes | Payment history. |
| `GET` | `/api/accounts/feed/` | Yes | Personalized feed. |
| `POST` | `/api/accounts/feed/mark-read/<feed_item_id>/` | Yes | Mark feed item read. |
| `POST` | `/api/accounts/feed/mark-all-read/` | Yes | Mark all feed read. |
| `GET` | `/api/accounts/feed/unread-count/` | Yes | Feed unread count. |

## Dashboards and Public Browse

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/dashboards/me/` | Yes | Route user to role dashboard. |
| `GET` | `/api/dashboards/fan/` | Yes | Fan dashboard. |
| `GET` | `/api/dashboards/club-admin/` | Yes | Club admin dashboard. |
| `GET` | `/api/dashboards/league-admin/` | Yes | League admin dashboard. |
| `GET` | `/api/dashboards/union-admin/` | Yes | Union admin dashboard. |
| `GET` | `/api/dashboards/super-admin/` | Yes | Super admin dashboard. |
| `GET` | `/api/dashboards/referee/` | Yes | Referee dashboard. |
| `GET` | `/api/dashboards/ticketing-officer/` | Yes | Ticketing officer dashboard. |
| `GET` | `/api/dashboards/sponsor/` | Yes | Sponsor dashboard. |
| `GET` | `/api/dashboards/public/fixtures/` | No | Public fixtures. |
| `GET` | `/api/dashboards/public/results/` | No | Public results. |
| `GET` | `/api/dashboards/public/standings/` | No | Public standings. |
| `GET` | `/api/dashboards/public/clubs/` | No | Public clubs. |
| `GET` | `/api/dashboards/public/unions/` | No | Public unions. |
| `GET` | `/api/dashboards/public/leagues/` | No | Public leagues. |
| `GET` | `/api/dashboards/public/competitions/` | No | Public competitions. |
| `GET` | `/api/dashboards/public/matches/<match_id>/` | No | Public match detail. |
| `GET` | `/api/dashboards/public/standings/calculate/` | No | Standings calculation/recompute endpoint. |

## Governance

Super-admin-only module for platform-wide governance configuration.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/governance/sport-variants/` | Super Admin | List sport variants. |
| `POST` | `/api/governance/sport-variants/` | Super Admin | Create sport variant. |
| `GET` | `/api/governance/sport-variants/<pk>/` | Super Admin | Retrieve sport variant. |
| `PATCH` | `/api/governance/sport-variants/<pk>/` | Super Admin | Partial update sport variant. |
| `PUT` | `/api/governance/sport-variants/<pk>/` | Super Admin | Full update sport variant. |
| `DELETE` | `/api/governance/sport-variants/<pk>/` | Super Admin | Delete sport variant. |
| `POST` | `/api/governance/sport-variants/<pk>/verify/` | Super Admin | Verify sport variant. |
| `GET` | `/api/governance/competition-formats/` | Super Admin | List competition formats. |
| `POST` | `/api/governance/competition-formats/` | Super Admin | Create competition format. |
| `GET` | `/api/governance/competition-formats/<pk>/` | Super Admin | Retrieve competition format. |
| `PATCH` | `/api/governance/competition-formats/<pk>/` | Super Admin | Partial update competition format. |
| `PUT` | `/api/governance/competition-formats/<pk>/` | Super Admin | Full update competition format. |
| `DELETE` | `/api/governance/competition-formats/<pk>/` | Super Admin | Delete competition format. |
| `POST` | `/api/governance/competition-formats/<pk>/verify/` | Super Admin | Verify competition format. |
| `GET` | `/api/governance/rules/` | Super Admin | List rules & standards. |
| `POST` | `/api/governance/rules/` | Super Admin | Create rule/standard. |
| `GET` | `/api/governance/rules/<pk>/` | Super Admin | Retrieve rule/standard. |
| `PATCH` | `/api/governance/rules/<pk>/` | Super Admin | Partial update rule/standard. |
| `PUT` | `/api/governance/rules/<pk>/` | Super Admin | Full update rule/standard. |
| `DELETE` | `/api/governance/rules/<pk>/` | Super Admin | Delete rule/standard. |
| `POST` | `/api/governance/rules/<pk>/publish/` | Super Admin | Publish rule/standard for league assignment. |
| `POST` | `/api/governance/rules/<pk>/unpublish/` | Super Admin | Unpublish rule/standard. |
| `GET` | `/api/governance/league-standards/` | Super Admin | List league-standard assignments. |
| `POST` | `/api/governance/league-standards/` | Super Admin | Publish standards to leagues. |
| `DELETE` | `/api/governance/league-standards/<pk>/` | Super Admin | Remove league-standard assignment. |
| `GET` | `/api/governance/leagues/<league_pk>/standards/` | Super Admin | List standards for a league. |

### Publish Standards to Leagues Request

```json
{
  "rule_ids": [1, 2],
  "league_ids": [10, 11],
  "notes": "Optional assignment notes"
}
```

## Sponsorships

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/sponsorships/register/` | Yes | Register sponsor account. |
| `GET/POST` | `/api/sponsorships/accounts/` | Yes | List/create sponsor accounts. |
| `GET/PATCH` | `/api/sponsorships/accounts/<account_id>/` | Yes | Sponsor account detail. |
| `GET/POST` | `/api/sponsorships/accounts/<account_id>/members/` | Yes | Sponsor account members. |
| `GET/POST` | `/api/sponsorships/packages/` | Yes/Admin depending on operation | Sponsor packages. |
| `GET/PATCH` | `/api/sponsorships/packages/<package_id>/` | Yes/Admin depending on operation | Sponsor package detail. |
| `POST` | `/api/sponsorships/packages/<package_id>/approve/` | Admin | Approve package. |
| `POST` | `/api/sponsorships/packages/<package_id>/reject/` | Admin | Reject package. |
| `GET/POST` | `/api/sponsorships/packages/<package_id>/benefits/` | Yes/Admin depending on operation | Package benefits. |
| `GET/POST` | `/api/sponsorships/packages/<package_id>/revenue-share-rules/` | Admin | Package revenue rules. |
| `GET/POST` | `/api/sponsorships/agreements/` | Yes | Sponsor agreements. |
| `GET/PATCH` | `/api/sponsorships/agreements/<agreement_id>/` | Yes | Agreement detail. |
| `POST` | `/api/sponsorships/agreements/<agreement_id>/approve/` | Admin | Approve agreement. |
| `POST` | `/api/sponsorships/agreements/<agreement_id>/reject/` | Admin | Reject agreement. |
| `POST` | `/api/sponsorships/agreements/<agreement_id>/activate/` | Admin | Activate agreement. |
| `GET/POST` | `/api/sponsorships/agreements/<agreement_id>/payment-schedules/` | Yes/Admin | Agreement payment schedules. |
| `GET/POST` | `/api/sponsorships/agreements/<agreement_id>/payments/` | Yes/Admin | Agreement payments. |
| `GET/POST` | `/api/sponsorships/agreements/<agreement_id>/revenue-share-rules/` | Admin | Agreement revenue rules. |
| `GET` | `/api/sponsorships/agreements/<agreement_id>/revenue-distributions/` | Admin | Agreement distributions. |
| `POST` | `/api/sponsorships/payments/<payment_id>/confirm/` | Admin | Confirm manual payment. |
| `POST` | `/api/sponsorships/payments/<payment_id>/reject/` | Admin | Reject payment. |
| `GET` | `/api/sponsorships/payments/<payment_id>/revenue-distributions/` | Admin | Payment distributions. |
| `POST` | `/api/sponsorships/agreements/<agreement_id>/flutterwave/initialize/` | Yes | Initialize sponsorship Flutterwave checkout. |
| `GET` | `/api/sponsorships/flutterwave/verify/` | No | Flutterwave redirect verification. |
| `POST` | `/api/sponsorships/flutterwave/webhook/` | No | Flutterwave webhook. |

## Ticketing

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/ticketing/matches/<match_id>/ticket-types/` | No | List ticket types for match. |
| `GET` | `/api/ticketing/orders/` | Yes | Current user's ticket orders. |
| `POST` | `/api/ticketing/orders/flutterwave/initialize/` | Yes | Create pending order and initialize Flutterwave checkout. |
| `GET` | `/api/ticketing/tickets/me/` | Yes | Current user's issued tickets. |
| `GET` | `/api/ticketing/flutterwave/verify/` | No | Verify Flutterwave ticket payment using `tx_ref` or `reference`. |
| `POST` | `/api/ticketing/flutterwave/webhook/` | No | Flutterwave ticket webhook. |
| `POST` | `/api/ticketing/validate/` | Ticketing/admin roles | Validate/check in a ticket. |

### Ticket Checkout Request

```json
{
  "ticket_type_id": 1,
  "quantity": 2
}
```

### Ticket Checkout Response

```json
{
  "message": "Flutterwave ticket checkout initialized successfully.",
  "order": {
    "id": 1,
    "status": "PENDING"
  },
  "tx_ref": "LOS-TICKET-1-...",
  "checkout_url": "https://checkout.flutterwave.com/..."
}
```

### Ticket Verification Request

```text
GET /api/ticketing/flutterwave/verify/?tx_ref=LOS-TICKET-1-...
```

### Ticket Validation Request

```json
{
  "scanned_code": "ticket-uuid-value",
  "match_id": 1
}
```

## Monitoring & Audit

Super-admin-only module for platform monitoring, audit trails, compliance, and security events.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/monitoring/anomalies/` | Super Admin | List anomalies. |
| `POST` | `/api/monitoring/anomalies/` | Super Admin | Create anomaly. |
| `GET` | `/api/monitoring/anomalies/<pk>/` | Super Admin | Retrieve anomaly. |
| `PATCH` | `/api/monitoring/anomalies/<pk>/` | Super Admin | Partial update anomaly. |
| `PUT` | `/api/monitoring/anomalies/<pk>/` | Super Admin | Full update anomaly. |
| `DELETE` | `/api/monitoring/anomalies/<pk>/` | Super Admin | Delete anomaly. |
| `POST` | `/api/monitoring/anomalies/<pk>/resolve/` | Super Admin | Resolve anomaly. |
| `GET` | `/api/monitoring/payments/` | Super Admin | List payment audit records. |
| `GET` | `/api/monitoring/payments/<pk>/` | Super Admin | Retrieve payment audit. |
| `GET` | `/api/monitoring/transactions/` | Super Admin | List transaction reconciliations. |
| `POST` | `/api/monitoring/transactions/` | Super Admin | Create reconciliation. |
| `GET` | `/api/monitoring/transactions/<pk>/` | Super Admin | Retrieve reconciliation. |
| `PATCH` | `/api/monitoring/transactions/<pk>/` | Super Admin | Partial update reconciliation. |
| `PUT` | `/api/monitoring/transactions/<pk>/` | Super Admin | Full update reconciliation. |
| `POST` | `/api/monitoring/transactions/<pk>/verify/` | Super Admin | Verify reconciliation. |
| `GET` | `/api/monitoring/system-logs/` | Super Admin | List system logs. |
| `GET` | `/api/monitoring/system-logs/<pk>/` | Super Admin | Retrieve system log. |
| `GET` | `/api/monitoring/compliance/` | Super Admin | List compliance trails. |
| `POST` | `/api/monitoring/compliance/` | Super Admin | Create compliance trail. |
| `GET` | `/api/monitoring/compliance/<pk>/` | Super Admin | Retrieve compliance trail. |
| `PATCH` | `/api/monitoring/compliance/<pk>/` | Super Admin | Partial update compliance trail. |
| `PUT` | `/api/monitoring/compliance/<pk>/` | Super Admin | Full update compliance trail. |
| `GET` | `/api/monitoring/data-access/` | Super Admin | List data access audit records. |
| `GET` | `/api/monitoring/data-access/<pk>/` | Super Admin | Retrieve data access audit. |
| `GET` | `/api/monitoring/security-events/` | Super Admin | List security events. |
| `POST` | `/api/monitoring/security-events/` | Super Admin | Create security event. |
| `GET` | `/api/monitoring/security-events/<pk>/` | Super Admin | Retrieve security event. |
| `POST` | `/api/monitoring/security-events/<pk>/resolve/` | Super Admin | Resolve security event. |

## RBAC

Super-admin-only module for managing role templates, permissions, permission bundles, user role assignments, user permission overrides, sessions, and impersonation.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/rbac/permissions/` | Super Admin | List all permissions. |
| `GET` | `/api/rbac/permissions/<pk>/` | Super Admin | Retrieve permission. |
| `GET/POST` | `/api/rbac/bundles/` | Super Admin | List or create permission bundles. |
| `GET/PUT/PATCH/DELETE` | `/api/rbac/bundles/<pk>/` | Super Admin | Retrieve, update, or delete permission bundle. |
| `GET/POST` | `/api/rbac/role-templates/` | Super Admin | List or create role templates. |
| `GET/PUT/PATCH/DELETE` | `/api/rbac/role-templates/<pk>/` | Super Admin | Retrieve, update, or delete role template. |
| `GET/POST` | `/api/rbac/assignments/` | Super Admin | List or create user role assignments. |
| `GET/PUT/PATCH/DELETE` | `/api/rbac/assignments/<pk>/` | Super Admin | Retrieve, update, or delete user role assignment. |
| `GET/POST` | `/api/rbac/overrides/` | Super Admin | List or create user permission overrides. |
| `GET/PUT/PATCH/DELETE` | `/api/rbac/overrides/<pk>/` | Super Admin | Retrieve, update, or delete permission override. |
| `GET` | `/api/rbac/sessions/` | Super Admin | List user sessions. |
| `GET/POST` | `/api/rbac/sessions/<pk>/` | Super Admin | Retrieve or revoke session. |
| `GET/POST` | `/api/rbac/impersonation/` | Super Admin | List impersonation sessions or start new impersonation. |
| `POST` | `/api/rbac/impersonation/<pk>/stop/` | Super Admin | Stop active impersonation session. |

## Current Frontend Endpoint Alignment Note

The backend currently has:

```text
/api/accounts/profile/
/api/accounts/notifications/
```

If a frontend calls:

```text
/api/profile/
/api/notifications/
```

those will return 404 unless aliases are added or the frontend path is corrected.
