#!/bin/sh

echo "📡 Waiting for PostgreSQL..."

while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done

echo "✅ PostgreSQL is up. Starting Django..."

python manage.py migrate
python manage.py collectstatic --noinput --clear
exec gunicorn backend.wsgi:application --bind 0.0.0.0:8000
