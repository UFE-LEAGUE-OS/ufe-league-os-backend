FROM python:3.12-slim

WORKDIR /app

ARG REQUIREMENTS_FILE=requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements*.txt /app/

RUN pip install --upgrade pip \
    && pip install -r "/app/${REQUIREMENTS_FILE}"

COPY backend /app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
