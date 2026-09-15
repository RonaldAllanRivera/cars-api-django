#!/bin/sh
# Container entrypoint. Render's free tier has no shell and no pre-deploy
# command, so everything a fresh database needs happens here, on every boot.
# Each step is idempotent; any failure stops the boot so the deploy shows red
# instead of serving a half-migrated app.
set -eu

echo "==> Applying migrations"
python manage.py migrate --noinput

echo "==> Ensuring the cache table exists"
python manage.py createcachetable

echo "==> Ensuring the admin account (ADMIN_EMAIL / ADMIN_PASSWORD)"
python manage.py ensure_admin

echo "==> Seeding makes and models into an empty catalog"
python manage.py seed_catalog --if-empty

# Sized for a 512 MB instance. Two workers keep the admin responsive while one
# is busy; threads let a worker serve API reads while another thread builds a
# ZIP (~120 s of downloads and Pillow resizes). The timeout sits above that.
# --max-requests recycles workers to cap slow memory growth from image work.
# The control socket (gunicorn 25.1+) is unused, and /app is read-only to this user.
echo "==> Starting gunicorn on port ${PORT:-8000}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --worker-class gthread \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --worker-tmp-dir /dev/shm \
    --no-control-socket \
    --forwarded-allow-ips "*" \
    --access-logfile - \
    --error-logfile -
