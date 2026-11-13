#!/bin/sh
set -e

echo "Running database migrations…"
flask --app wsgi db upgrade

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  echo "Seeding fictional demo data (this resets the demo tables)…"
  python manage.py seed
fi

echo "Starting ReTurn API…"
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  wsgi:app
