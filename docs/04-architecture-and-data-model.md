# 04. Architecture and Data Model Notes

## High-Level Architecture

```text
React/Vite Frontend
       |
       | HTTPS / JSON / JWT
       v
Django REST Framework API
       |
       | ORM
       v
PostgreSQL
```

Extra integrations:

```text
Brevo SMTP       -> OTP emails
Google OAuth     -> Google sign-in
Flutterwave      -> Sponsorship and ticket payments
Swagger/OpenAPI  -> API discovery for devs and QA
```

## Apps and Important Models

### `accounts`

| Model | Purpose |
|---|---|
| `User` | Custom user model with role support and email login. |
| `Club` | Club entity used in account-related ownership and role flows. |
| `AuditLog` | Audit records for important actions. |
| `EmailOTP` | OTP verification records. |
| `Follow` | User follows for clubs, leagues, unions, etc. |
| `NotificationPreference` | User notification settings. |
| `InterestPreference` | User sports/team/content preferences. |
| `Wallet` | User wallet placeholder. |
| `PaymentHistory` | User payment history placeholder. |
| `FeedItem` | Personalized feed item. |

### `dashboards`

| Model | Purpose |
|---|---|
| `Union` | Sports federation/union level, such as Uganda Rugby Union. |
| `League` | League under a union. |
| `Competition` | Season/competition under a league. |
| `Match` | Fixture/result between home and away clubs. |
| `Standing` | Table/standings record. |

### `governance`

| Model | Purpose |
|---|---|
| `SportVariant` | Rugby 15s/7s, football 11s/9s, basketball variants, etc. |
| `CompetitionFormat` | League, knockout, pool, hybrid formats. |
| `Rule` | Rules and standards documents. |
| `LeagueStandard` | Published standards applied to leagues. |

### `sponsorships`

| Model | Purpose |
|---|---|
| `SponsorAccount` | Individual/corporate sponsor profile. |
| `SponsorAccountMember` | Members of corporate sponsor accounts. |
| `SponsorPackage` | Sponsorship packages. |
| `SponsorBenefit` | Benefits attached to packages. |
| `SponsorAgreement` | Sponsor agreement lifecycle. |
| `SponsorPaymentSchedule` | Scheduled payments for agreements. |
| `SponsorPayment` | Payment records. |
| `RevenueShareRule` | Rules for revenue distribution. |
| `RevenueDistribution` | Distribution records. |
| `SponsorWorkflowEvent` | Sponsor workflow audit events. |

### `ticketing`

| Model | Purpose |
|---|---|
| `TicketType` | Ticket category for a match, such as Ordinary or VIP. |
| `TicketOrder` | Fan purchase order. |
| `TicketOrderItem` | Quantity of one ticket type in an order. |
| `Ticket` | Issued ticket after payment confirmation. |
| `TicketValidationLog` | Scan/check-in attempt audit log. |

## Ticketing Flow

```text
Fan chooses ticket type
       |
       v
Backend creates TicketOrder + TicketOrderItem as PENDING
       |
       v
Backend initializes Flutterwave checkout
       |
       v
Fan pays on Flutterwave
       |
       v
Backend verifies payment with Flutterwave
       |
       v
Backend marks TicketOrder as PAID
       |
       v
Backend creates Ticket records
       |
       v
Ticketing officer validates ticket_code at gate
```

Important rule:

```text
Tickets are not issued before payment verification.
```

## Sponsorship Payment Flow

```text
Sponsor agreement is created
       |
       v
Backend initializes Flutterwave sponsorship checkout
       |
       v
Sponsor pays
       |
       v
Backend verifies payment
       |
       v
Payment is confirmed and sponsorship workflow continues
```

## Why Services Exist

Payment and order logic should not live only in views. The service files hold business rules:

| Service | Purpose |
|---|---|
| `sponsorships/flutterwave.py` | Shared Flutterwave request/verification helpers. |
| `ticketing/services/orders.py` | Ticket order creation, ticket issuing, validation/check-in. |
| `ticketing/services/flutterwave_gateway.py` | Ticket Flutterwave payloads, verification, webhook handling. |

This makes tests easier and keeps views focused on request/response behavior.
