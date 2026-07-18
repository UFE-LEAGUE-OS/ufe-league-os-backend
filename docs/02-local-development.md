# 02. Local Development Guide

## Prerequisites

Install:

- Git
- Docker Desktop
- VS Code
- A terminal such as Git Bash / MINGW64 on Windows

You do not need to install PostgreSQL locally because Docker Compose runs PostgreSQL for you.

## Repository Setup

```bash
cd /k/Keith/Workspaces/ApprenticeshipProject/Codebase/UFE-League-OS
git clone https://github.com/UFE-LEAGUE-OS/ufe-league-os-backend.git
cd ufe-league-os-backend
cp .env.example .env
```

## Start Containers

```bash
docker compose up -d --build
docker compose ps
```

Expected services:

```text
league_os_db
league_os_backend
```

## Run Migrations

```bash
docker compose exec backend python manage.py migrate
```

## Create a Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

Open admin:

```text
http://localhost:8000/admin/
```

## Health Check

```bash
curl http://localhost:8000/api/health/
```

Expected response:

```json
{
  "status": "OK",
  "service": "League OS Backend API",
  "version": "sprint-1-foundation"
}
```

## Useful Development Commands

### Logs

```bash
docker compose logs backend --tail=200
docker compose logs -f backend
```

### Django checks

```bash
docker compose exec backend python manage.py check
```

### Migrations

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py makemigrations --check --dry-run
```

### Tests

```bash
docker compose exec backend python manage.py test
docker compose exec backend python manage.py test accounts
docker compose exec backend python manage.py test dashboards
docker compose exec backend python manage.py test governance
docker compose exec backend python manage.py test sponsorships
docker compose exec backend python manage.py test ticketing
```

The Django suite is the maintained application test suite. Run it with:

```bash
docker compose exec backend python manage.py test -v 1
```

The legacy pytest suite uses a test-only image so pytest plugins are not added
to the production runtime. Build that image with:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  build backend
```

Run the complete pytest suite:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  run --rm backend \
  python -m pytest -q
```

Run one pytest module:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  run --rm backend \
  python -m pytest backend/tests/test_account_roles.py -q
```

Run one pytest test:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  run --rm backend \
  python -m pytest \
  backend/tests/test_account_roles.py::TestClassName::test_name \
  -q
```

### Formatting and linting

```bash
docker compose exec backend black .
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend ruff check . --fix
```

## Reset Local Database

Use this only when you are okay losing local data.

```bash
docker compose down -v
docker compose up -d --build
docker compose exec backend python manage.py migrate
```

## Common Local Issues

### Backend container starts then disappears

Run:

```bash
docker compose logs backend --tail=200
```

Read the first Python traceback.

### Missing Python package

Example:

```text
ModuleNotFoundError: No module named 'google'
```

Fix by adding the package to `backend/requirements.txt`, then rebuild:

```bash
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

### Template watcher crash

If Django reports an input/output error watching `/app/templates`, keep project templates inside an installed app such as:

```text
backend/dashboards/templates/
```

and keep this setting:

```python
"DIRS": []
```
