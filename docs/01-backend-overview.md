# 01. Backend Overview

## Purpose

The League OS backend is the API layer for a multi-role sports management and fan engagement system. It is designed for Ugandan sports organizations, clubs, leagues, unions/federations, fans, sponsors, referees, and ticketing teams.

The backend is responsible for:

- User identity and authentication.
- Role-based access control.
- Public sports browsing.
- Role dashboards.
- Governance configuration for sports, formats, and rules.
- Sponsorship workflows and sponsor payments.
- Match ticket purchase and ticket validation.
- API documentation through Swagger/OpenAPI.
- Dockerized local development and CI-ready testing.

## Main Django Apps

| App | Purpose |
|---|---|
| `accounts` | Users, roles, registration, login, OTP, password reset, profiles, preferences, follows, wallet, feed, RBAC helpers. |
| `dashboards` | Unions, leagues, competitions, matches, standings, public browse endpoints, role dashboard endpoints. |
| `governance` | Sport variants, competition formats, rules, and league standards. |
| `sponsorships` | Sponsor accounts, packages, agreements, payment schedules, Flutterwave sponsorship payments, revenue rules/distributions. |
| `ticketing` | Match ticket types, ticket orders, Flutterwave ticket checkout, ticket issuing, fan tickets, validation/check-in logs. |
| `config` | Project settings, root URLs, ASGI/WSGI, health endpoint, API landing page. |

## Core Runtime Flow

```text
Frontend / Swagger / API Client
        |
        v
Django URL Router
        |
        v
DRF Function-Based Views
        |
        v
Serializers + Services + Models
        |
        v
PostgreSQL
```

For payments:

```text
Frontend starts checkout
        |
        v
Backend creates pending order/agreement payment
        |
        v
Backend initializes Flutterwave
        |
        v
User pays on Flutterwave checkout page
        |
        v
Backend verifies transaction with Flutterwave
        |
        v
Backend confirms payment and performs business action
```

For FAN-004 ticketing, the business action is issuing tickets.

## Current Roles

The custom user model supports these roles:

| Role | Typical Use |
|---|---|
| `FAN` | Public/fan account, follows clubs, buys tickets, receives feed/preference features. |
| `CLUB_ADMIN` | Manages club-level operations and users. |
| `LEAGUE_ADMIN` | Manages league/competition-level operations. |
| `UNION_ADMIN` | Manages union/federation-level governance and administration. |
| `SUPER_ADMIN` | Platform-level administration. |
| `REFEREE` | Referee/match official dashboard and role. |
| `TICKETING_OFFICER` | Validates/checks in tickets at match entry. |
| `SPONSOR` | Sponsor account/member workflows. |

## Authentication

The backend uses Simple JWT. Login returns access and refresh tokens. Frontend clients should send authenticated requests using:

```http
Authorization: Bearer <access_token>
```

## API Documentation

The backend exposes Swagger/OpenAPI at:

```text
GET /api/docs/
GET /api/schema/
```

The root API JSON discovery endpoint is:

```text
GET /api/
```

The visual backend landing page is:

```text
GET /
```
