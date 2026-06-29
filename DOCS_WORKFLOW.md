# Documentation Update Workflow

Use this workflow to add this documentation pack to the backend repository.

## 1. Create a docs branch

```bash
cd /k/Keith/Workspaces/ApprenticeshipProject/Codebase/UFE-League-OS/ufe-league-os-backend

git switch develop
git pull origin develop
git switch -c docs/backend-documentation
```

If you want these docs on top of the ticketing branch before merging, use:

```bash
git switch feat/fan-004-ticket-purchase
git pull origin feat/fan-004-ticket-purchase
git switch -c docs/backend-documentation
```

## 2. Copy files

Copy:

```text
README.md
docs/
```

into the repo root.

## 3. Review

```bash
git status
git diff --stat
git diff
```

## 4. Optional backend verification

Docs do not affect runtime, but you can still run:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend black --check .
docker compose exec backend ruff check .
docker compose exec backend python manage.py test
```

## 5. Commit

```bash
git add README.md docs
git commit -m "Document backend setup APIs DevOps QA and payments"
```

## 6. Push

```bash
git push -u origin docs/backend-documentation
```

## 7. Pull Request

Manual PR:

```text
Base: develop
Compare: docs/backend-documentation
Title: Document backend setup APIs DevOps QA and payments
```

PR body:

```md
## Summary
- Updates backend README
- Adds backend overview documentation
- Adds local development guide
- Adds environment variable reference
- Adds API reference for accounts, dashboards, governance, sponsorships, and ticketing
- Adds frontend integration guide
- Adds DevOps deployment guide
- Adds QA test plan
- Adds Flutterwave payment flow documentation
- Adds troubleshooting guide
- Adds current backend feature status

## Tests
Documentation-only change. Existing backend checks can still be run:
- docker compose exec backend python manage.py check
- docker compose exec backend python manage.py makemigrations --check --dry-run
- docker compose exec backend black --check .
- docker compose exec backend ruff check .
- docker compose exec backend python manage.py test
```
