from pathlib import Path

compose_path = Path("docker-compose.yml")

compose_path.write_text(
"""services:
  db:
    image: postgres:16-alpine
    container_name: league_os_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-league_os}
      POSTGRES_USER: ${POSTGRES_USER:-league_os_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-league_os_password}
    volumes:
      - league_os_postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: league_os_backend
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DB_HOST: db
      DB_PORT: 5432
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
    command: >
      sh -c "python manage.py migrate &&
            python manage.py runserver 0.0.0.0:8000"
    volumes:
      - ./backend:/app
      - league_os_media:/app/media
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  league_os_postgres_data:
  league_os_media:
""",
    newline="\n",
)

env_example_path = Path(".env.example")

if env_example_path.exists():
    env_example = env_example_path.read_text()

    if "FLUTTERWAVE_MEMBERSHIP_REDIRECT_URL" not in env_example:
        env_example = env_example.replace(
            "FLUTTERWAVE_TICKET_REDIRECT_URL=http://localhost:8000/api/ticketing/flutterwave/verify/\n",
            "FLUTTERWAVE_TICKET_REDIRECT_URL=http://localhost:8000/api/ticketing/flutterwave/verify/\n"
            "FLUTTERWAVE_MEMBERSHIP_REDIRECT_URL=http://localhost:8000/api/memberships/flutterwave/verify/\n",
        )

    if "FLUTTERWAVE_MEMBERSHIP_PAYMENT_TITLE" not in env_example:
        env_example = env_example.replace(
            "FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment\n",
            "FLUTTERWAVE_TICKET_PAYMENT_TITLE=League OS Match Ticket Payment\n"
            "FLUTTERWAVE_MEMBERSHIP_PAYMENT_TITLE=League OS Membership Payment\n",
        )

    if "MEMBERSHIP_DEMO_CHECKOUT_ENABLED" not in env_example:
        env_example += """

# =========================================================
# Local demo checkout toggles
# =========================================================
# Keep these False unless you intentionally want demo checkout without real payment.
TICKETING_DEMO_CHECKOUT_ENABLED=False
MEMBERSHIP_DEMO_CHECKOUT_ENABLED=False
"""

    env_example_path.write_text(env_example, newline="\n")

print("docker-compose.yml checked and .env.example membership variables confirmed.")
