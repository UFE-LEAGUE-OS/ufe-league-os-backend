# 11. Current Backend Feature Status

This document summarizes what the backend supports up to the FAN-004 ticketing work.

## Foundation

| Area | Status |
|---|---|
| Dockerized backend | Done |
| PostgreSQL Docker database | Done |
| Django REST Framework setup | Done |
| Health endpoint | Done |
| Swagger/OpenAPI docs | Done |
| Root backend landing page | Done |
| GitHub Actions CI | Present |
| Black/Ruff formatting and linting | Present |
| Full Django test suite | Present |

## Accounts and Authentication

| Feature | Status |
|---|---|
| Custom user model | Done |
| User roles | Done |
| Registration | Done |
| Login | Done |
| JWT authentication | Done |
| Email OTP verification | Done |
| Resend OTP | Done |
| Password reset request/confirm | Done |
| Profile endpoint | Done |
| Avatar remove endpoint | Done |
| Google auth endpoint | Done |
| Role-based user creation endpoints | Done |
| Follow/unfollow | Done |
| Notification preferences | Done |
| Interest preferences | Done |
| Wallet/payment history placeholders | Done |
| Personalized feed endpoints | Done |

## Dashboards and Public Browse

| Feature | Status |
|---|---|
| Role dashboard router | Done |
| Fan dashboard | Done |
| Club admin dashboard | Done |
| League admin dashboard | Done |
| Union admin dashboard | Done |
| Super admin dashboard | Done |
| Referee dashboard | Done |
| Ticketing officer dashboard | Done |
| Sponsor dashboard | Done |
| Public fixtures/results/standings | Done |
| Public clubs/unions/leagues/competitions | Done |
| Public match detail | Done |
| Standing calculation endpoint | Done |

## Governance

| Feature | Status |
|---|---|
| Sport variants | Done |
| Competition formats | Done |
| Rules | Done |
| Publish/unpublish rules | Done |
| League standards | Done |
| Verification actions | Done |

## Sponsorships

| Feature | Status |
|---|---|
| Sponsor registration | Done |
| Sponsor accounts | Done |
| Sponsor account members | Done |
| Sponsor packages | Done |
| Package benefits | Done |
| Package approval/rejection | Done |
| Sponsor agreements | Done |
| Agreement approval/rejection/activation | Done |
| Payment schedules | Done |
| Sponsor payments | Done |
| Manual payment confirmation/rejection | Done |
| Revenue share rules | Done |
| Revenue distributions | Done |
| Flutterwave sponsorship checkout | Done |
| Flutterwave sponsorship verify/webhook | Done |

## FAN-004 Ticketing

| Feature | Status |
|---|---|
| Ticket type model | Done |
| Ticket order model | Done |
| Ticket order item model | Done |
| Ticket model | Done |
| Validation log model | Done |
| Public match ticket type listing | Done |
| Fan ticket checkout initialization | Done |
| Flutterwave ticket payment verification | Done |
| Ticket issuing after verified payment | Done |
| Duplicate verification protection | Done |
| Fan ticket listing | Done |
| Ticketing officer validation/check-in | Done |
| Ticketing tests | Done |

## Current Known Integration Notes

| Note | Impact |
|---|---|
| Frontend should call `/api/accounts/profile/`, not `/api/profile/`. | Avoid frontend 404. |
| Frontend should call `/api/accounts/notifications/`, not `/api/notifications/`. | Avoid frontend 404. |
| Some Swagger schema warnings exist for function-based sponsorship views. | Does not block runtime but should be cleaned later. |
| Flutterwave test mode should be used locally/staging. | Avoid real payment risk. |

## Recommended Next Backend Documentation Improvements

- Add Postman collection.
- Add seed data command or fixture for QA.
- Add OpenAPI schema examples using `@extend_schema`.
- Add ADR documents for payment design and RBAC decisions.
- Add frontend/backend endpoint contract tests.
