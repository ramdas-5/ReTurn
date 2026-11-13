#!/bin/sh
set -e

echo "Running database migrations…"
flask --app wsgi db upgrade

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  if [ "${SEED_DEMO_DATA_RESET:-false}" = "true" ]; then
    echo "Rebuilding the fictional demo data (destructive)…"
    python manage.py seed
  else
    # Safe default: seed only when the database has no users yet.
    echo "Seeding fictional demo data if the database is empty…"
    python manage.py seed-if-empty
  fi
fi

# Render/Railway inject PORT; Docker Compose leaves it unset (5000).
BIND_PORT="${PORT:-5000}"
echo "Starting ReTurn API on 0.0.0.0:${BIND_PORT}…"
exec gunicorn \
  --bind "0.0.0.0:${BIND_PORT}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  wsgi:app
