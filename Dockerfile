# Image for the web app + REST API. The LiveKit voice worker runs as a separate
# process/service (see docker-compose) because it needs audio + provider keys.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-voice.txt .
# Core deps only in the image; the optional voice/redis/celery lines are
# installed in the services that need them.
RUN pip install --no-cache-dir Flask==3.0.3 Flask-SQLAlchemy==3.1.1 \
    Flask-Login==0.6.3 PyJWT numpy scikit-learn requests redis celery

COPY . .

# Seed on first run, then serve the app + API.
CMD ["sh", "-c", "python seed.py || true; python run_api.py"]
