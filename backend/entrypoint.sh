#!/bin/sh
set -e

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run production checks
echo "Running Django production checks..."
python manage.py check --deploy --fail-level CRITICAL

# Start Gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --log-level="info" \
    --log-file=- \
    --access-logfile=- \
    --error-logfile=-

