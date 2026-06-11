# UFE League OS Backend

Django REST backend for **League OS**, a multi-tenant sports fan engagement, ticketing, membership, sponsorship, and league management platform.

The backend provides authentication, email OTP verification, profile management, avatar upload, and role-based dashboard endpoints for different sports platform users.

---

## Current Backend Foundation Status

The backend foundation currently includes:

* Dockerized Django development environment
* PostgreSQL database
* Django REST Framework API setup
* Custom user model with role support
* Email or phone number login
* JWT authentication
* Email OTP verification
* Authenticated profile update API
* Avatar upload and removal
* Role-based dashboard endpoints
* Automated backend tests
* GitHub Actions CI workflow

---

## Tech Stack

* Python 3.12
* Django
* Django REST Framework
* PostgreSQL
* Docker
* Docker Compose
* JWT Authentication
* GitHub Actions CI
* Black
* Ruff

---

## User Roles

The backend currently supports the following user roles:

* Fan / Member
* Club Admin
* League Admin
* Union Admin
* Super Admin
* Referee / Match Official
* Ticketing Officer
* Sponsor

---

## Local Setup

Clone the repository:

```bash
git clone https://github.com/UFE-LEAGUE-OS/ufe-league-os-backend.git
cd ufe-league-os-backend
```

Copy the environment file:

```bash
cp .env.example .env
```

Start the Docker containers:

```bash
docker compose up -d --build
```

Check that the containers are running:

```bash
docker compose ps
```

Run database migrations:

```bash
docker compose exec backend python manage.py migrate
```

Run the automated tests:

```bash
docker compose exec backend python manage.py test
```

Check the health endpoint:

```bash
curl -i http://localhost:8000/api/health/
```

Expected response:

```json
{
  "status": "OK",
  "service": "League OS Backend API",
  "version": "sprint-1-foundation"
}
```

---

## Environment Variables

The project uses `.env` for local environment configuration.

Create your local `.env` file from the example:

```bash
cp .env.example .env
```

Important local Docker setting:

```env
DB_HOST=db
```

In GitHub Actions CI, the database host is different:

```env
DB_HOST=localhost
```

This difference is correct because Docker Compose and GitHub Actions use different network setups.

---

## Useful Development Commands

Run Django system checks:

```bash
docker compose exec backend python manage.py check
```

Check for missing migrations:

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run
```

Run migrations:

```bash
docker compose exec backend python manage.py migrate
```

Run tests:

```bash
docker compose exec backend python manage.py test
```

Format code with Black:

```bash
docker compose exec backend black .
```

Check linting with Ruff:

```bash
docker compose exec backend ruff check .
```

View backend logs:

```bash
docker compose logs -f backend
```

Build the Docker image:

```bash
docker build -t ufe-league-os-backend:test .
```

---

## API Endpoints

### Health

| Method | Endpoint       | Description          |
| ------ | -------------- | -------------------- |
| GET    | `/api/health/` | Backend health check |

---

### Accounts

| Method | Endpoint                        | Description                          |
| ------ | ------------------------------- | ------------------------------------ |
| POST   | `/api/accounts/register/`       | Register a new fan account           |
| POST   | `/api/accounts/verify-otp/`     | Verify email OTP                     |
| POST   | `/api/accounts/resend-otp/`     | Resend email OTP                     |
| POST   | `/api/accounts/login/`          | Login with email or phone number     |
| GET    | `/api/accounts/me/`             | Get authenticated user               |
| GET    | `/api/accounts/profile/`        | Get authenticated user profile       |
| PATCH  | `/api/accounts/profile/`        | Update user profile or upload avatar |
| DELETE | `/api/accounts/profile/avatar/` | Remove user avatar                   |

---

### Dashboards

| Method | Endpoint                             | Description                                |
| ------ | ------------------------------------ | ------------------------------------------ |
| GET    | `/api/dashboards/me/`                | Resolve the authenticated user's dashboard |
| GET    | `/api/dashboards/fan/`               | Fan dashboard                              |
| GET    | `/api/dashboards/club-admin/`        | Club admin dashboard                       |
| GET    | `/api/dashboards/league-admin/`      | League admin dashboard                     |
| GET    | `/api/dashboards/union-admin/`       | Union admin dashboard                      |
| GET    | `/api/dashboards/super-admin/`       | Super admin dashboard                      |
| GET    | `/api/dashboards/referee/`           | Referee dashboard                          |
| GET    | `/api/dashboards/ticketing-officer/` | Ticketing officer dashboard                |
| GET    | `/api/dashboards/sponsor/`           | Sponsor dashboard                          |

---

## Authentication

Login uses an `identifier` field.

The identifier can be either an email address or a phone number.

Example email login:

```json
{
  "identifier": "fan@example.com",
  "password": "StrongPass123"
}
```

Example phone login:

```json
{
  "identifier": "+256700000000",
  "password": "StrongPass123"
}
```

Successful login returns:

* access token
* refresh token
* user role
* frontend dashboard route
* backend dashboard route
* authenticated user details

Protected endpoints require this header:

```text
Authorization: Bearer <access_token>
```

---

## Email OTP in Development

The project uses Django's console email backend during local development.

When a user registers, the OTP is printed in the backend logs.

To view the OTP:

```bash
docker compose logs --tail=100 backend
```

Look for a line like:

```text
Your League OS verification code is: 123456
```

Use that code to verify the user through:

```text
POST /api/accounts/verify-otp/
```

---

## Profile and Avatar Upload

Authenticated users can update their profile using:

```text
PATCH /api/accounts/profile/
```

Allowed profile update fields:

* first_name
* last_name
* phone_number
* avatar

Avatar upload rules:

* Maximum size: 2MB
* Allowed formats: JPEG, PNG, WEBP, GIF

To remove an avatar:

```text
DELETE /api/accounts/profile/avatar/
```

---

## Role-Based Dashboards

The dashboard resolver endpoint is:

```text
GET /api/dashboards/me/
```

It returns the correct dashboard information for the authenticated user's role.

Example response fields:

```json
{
  "role": "FAN",
  "frontend_dashboard_route": "/dashboard/fan",
  "backend_dashboard_route": "/api/dashboards/fan/",
  "dashboard": {
    "title": "Fan Dashboard"
  }
}
```

Users can only access the dashboard endpoint for their own role.

For example:

* A FAN can access `/api/dashboards/fan/`
* A FAN cannot access `/api/dashboards/club-admin/`
* Wrong-role access returns `403 Forbidden`
* Unauthenticated access returns `401 Unauthorized`

---

## Testing with Postman

Recommended Postman flow:

1. Health Check
2. Register User
3. Copy OTP from backend logs
4. Verify OTP
5. Login with Email
6. Login with Phone
7. Get Current User
8. Get Profile
9. Update Profile
10. Upload Avatar
11. Remove Avatar
12. Test role-based dashboard access

Use a Postman environment with:

| Variable        | Value                    |
| --------------- | ------------------------ |
| `base_url`      | `http://localhost:8000`  |
| `email`         | saved after registration |
| `phone`         | saved after registration |
| `otp_code`      | copied from backend logs |
| `access_token`  | saved after login        |
| `refresh_token` | saved after login        |

---

## GitHub Actions CI

The repository includes a GitHub Actions workflow at:

```text
.github/workflows/backend-ci.yml
```

The CI workflow runs on pushes to:

* `main`
* `develop`
* `feature/**`

It also runs on pull requests into:

* `main`
* `develop`

The CI checks:

* Black formatting
* Ruff linting
* Django system check
* Missing migrations
* Database migrations
* Automated tests
* Docker image build

---

## Final Local Check Before Pushing

Before pushing changes, run:

```bash
docker compose exec backend black .
docker compose exec backend ruff check .
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test
docker build -t ufe-league-os-backend:test .
git status
```

Expected result:

* Black passes
* Ruff passes
* Django check passes
* No missing migrations
* Tests pass
* Docker image builds
* Working tree is clean or only expected files are modified

---

## Git Workflow

Do not work directly on `main`.

Recommended branch flow:

```text
main
develop
feature/backend-foundation
```

Current backend foundation work should be completed on:

```text
feature/backend-foundation
```

After checks pass, open a pull request into:

```text
develop
```

---

## License

Internal project for UFE League OS development.
