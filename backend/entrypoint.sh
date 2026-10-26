#!/bin/sh
set -e

# Apply migrations on every start (safe: no-op if already applied)
python manage.py migrate --noinput

# Run whatever command docker-compose passes (runserver now, gunicorn later)
exec "$@"
