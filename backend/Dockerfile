# syntax=docker/dockerfile:1

# Production image for the Django API + admin (Render free tier: 512 MB RAM, 0.1 CPU).
# docker-compose.yml builds the same image for development with REQUIREMENTS=dev.
FROM python:3.13-slim

ARG REQUIREMENTS=base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# UID 1000 matches the usual host user, so files written to a bind mount in
# development stay owned by you.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

# Dependencies first: this layer is reused until a requirements file changes.
# Every dependency ships a manylinux wheel (psycopg[binary], Pillow), so no
# compiler or system libraries are needed.
COPY requirements/ requirements/
RUN pip install -r "requirements/${REQUIREMENTS}.txt"

# Source stays root-owned: the app user can read it but not rewrite it.
COPY . .

# Hashed, compressed static files for WhiteNoise, baked into the image. The key
# only satisfies settings import; nothing signed at build time is kept.
RUN APP_KEY=collectstatic-build-only APP_DEBUG=false python manage.py collectstatic --noinput \
    && chmod +x bin/start.sh

USER app

EXPOSE 8000

CMD ["bin/start.sh"]
