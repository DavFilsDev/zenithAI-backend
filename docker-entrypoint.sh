#!/bin/sh
set -eu

if [ -n "${DATABASE_URL_UNPOOLED:-}" ]; then
    DATABASE_URL="$DATABASE_URL_UNPOOLED" python manage.py migrate --noinput
else
    python manage.py migrate --noinput
fi
python manage.py collectstatic --noinput

exec "$@"
