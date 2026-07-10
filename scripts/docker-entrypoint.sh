#!/bin/sh
set -e

mkdir -p /app/data /app/media /app/staticfiles /app/media/excel_uploads

echo "==> migrate..."
python manage.py migrate --noinput

echo "==> collectstatic..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "==> ادمین اولیه..."
python manage.py ensure_initial_setup

echo "==> http://0.0.0.0:8000"
exec python manage.py runserver 0.0.0.0:8000