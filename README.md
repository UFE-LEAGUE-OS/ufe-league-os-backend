# UFE League OS Backend

Django REST backend for **League OS**, a multi-role sports platform for fan engagement, public sports data, ticketing, sponsorships, governance, and role-based dashboards.

The backend currently supports:

- User registration, login, Google authentication, OTP verification, password reset, profile management, avatar management, preferences, follows, wallet/payment history, and personalized feed endpoints.
- Role-based dashboards for fans, club admins, league admins, union admins, super admins, referees, ticketing officers, and sponsors.
- Public browse endpoints for fixtures, results, standings, clubs, unions, leagues, competitions, and match details.
- Sports governance configuration for sport variants, competition formats, rules, and league standards.
- Sponsorship accounts, packages, agreements, payment schedules, Flutterwave sponsorship checkout, payment confirmation, workflow events, and revenue distribution logic.
- Match ticket purchase flow under **FAN-004**, including ticket type listing, ticket order creation, Flutterwave checkout initialization, payment verification, ticket issuing, fan ticket listing, and ticket validation/check-in.

## Quick Links

| Area | Local URL |
|---|---|
| Backend landing page | <http://localhost:8000/> |
| API JSON landing page | <http://localhost:8000/api/> |
| Health check | <http://localhost:8000/api/health/> |
| Swagger/OpenAPI docs | <http://localhost:8000/api/docs/> |
| OpenAPI schema | <http://localhost:8000/api/schema/> |
| Django admin | <http://localhost:8000/admin/> |

## Tech Stack

- Python 3.12
- Django 5.2.14
- Django REST Framework
- PostgreSQL 16
- Docker and Docker Compose
- Simple JWT authentication
- Django Channels / Daphne
- drf-spectacular Swagger/OpenAPI documentation
- Flutterwave payment integration
- Black formatting
- Ruff linting
- GitHub Actions CI

## Documentation Map

Read these files depending on your role:

| Role | Start Here |
|---|---|
| New backend developer | `docs/01-backend-overview.md`, then `docs/02-local-development.md` |
| Frontend developer | `docs/05-api-reference.md`, `docs/06-frontend-integration-guide.md` |
| QA tester | `docs/08-qa-test-plan.md`, `docs/10-troubleshooting.md` |
| DevOps engineer | `docs/03-environment-variables.md`, `docs/07-devops-deployment-guide.md` |
| Product owner / project reviewer | `docs/01-backend-overview.md`, `docs/11-current-feature-status.md` |
| Payment integration reviewer | `docs/09-flutterwave-payment-flows.md` |

## Local Setup

```bash
git clone https://github.com/UFE-LEAGUE-OS/ufe-league-os-backend.git
cd ufe-league-os-backend
cp .env.example .env
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test
```

## Standard Quality Checks

Run these before every commit or pull request:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
```

If Black fails:

```bash
docker compose exec backend black .
docker compose exec backend black --check .
```

If Ruff has fixable issues:

```bash
docker compose exec backend ruff check . --fix
docker compose exec backend ruff check .
```

## Branch and PR Workflow

Use feature branches. Do not commit directly to `develop`.

```bash
git switch develop
git pull origin develop
git switch -c feat/short-feature-name

# work, test, commit

git push -u origin feat/short-feature-name
```

Open a pull request with:

- Base branch: `develop`
- Compare branch: your feature branch

Include test evidence in the PR description.
