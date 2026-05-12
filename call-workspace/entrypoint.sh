#!/bin/bash
set -e

# Only the web (gunicorn) process runs migrations and collectstatic
if [[ "$1" == gunicorn* ]]; then
    echo "==> Running migrations..."
    python manage.py migrate --noinput

    echo "==> Collecting static files..."
    python manage.py collectstatic --noinput --clear
fi

echo "==> Starting process: $@"
exec "$@"
