# syntax=docker/dockerfile:1
# One multi-stage build for every portal image. Targets:
#   web         production web pod (gunicorn; the chart supplies the command)
#   worker      production django-tasks worker (science stack from the worker lock)
#   web-dev     web + dev/test tools, runserver with autoreload (Skaffold)
#   worker-dev  worker + dev/test tools, db_worker --reload (Skaffold)
# Build:  docker build --target web -t bgc-data-portal-website django

# ── Frontend bundle (React + Vite) ───────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The base path is baked into the bundle so chunk imports resolve through the
# ingress prefix. Release images keep the production prefix; local builds pass
# --build-arg VITE_BASE_PATH=/static/dashboard/ (see skaffold.yaml).
ARG VITE_BASE_PATH=/finn-srv/mgnify-bgcs/static/dashboard/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
# vite.config.ts writes to ../static/dashboard, i.e. /src/static/dashboard
RUN npm run build

# ── User docs (Quarto website served at /docs/) ──────────────────────────────
FROM ghcr.io/quarto-dev/quarto:1.8.25 AS docs
WORKDIR /src/docs
COPY docs/ ./
RUN quarto render

# ── Python base ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential python3-dev libffi-dev libssl-dev git curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# ── Production web ───────────────────────────────────────────────────────────
FROM base AS web
COPY requirements-web.lock .
RUN pip install -r requirements-web.lock
COPY . .
COPY --from=frontend /src/static/dashboard ./static/dashboard
COPY --from=docs /src/docs/_site ./docs/_site
# Pre-collect static files so the image serves them without a writable volume;
# the chart may re-run collectstatic at start, which is idempotent.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
EXPOSE 8000
# The pod runs as uid 7123 / gid 1347 (chart podSecurityContext); staticfiles
# and data dirs must be writable by that group.
RUN chgrp -R 1347 /app && chmod -R g+w /app

# ── Production worker ────────────────────────────────────────────────────────
FROM base AS worker
COPY requirements-worker.lock .
RUN pip install -r requirements-worker.lock
COPY . .

# ── Dev variants (Skaffold syncs source into /app) ───────────────────────────
FROM base AS web-dev
COPY requirements-web.lock requirements-dev.txt ./
RUN pip install -r requirements-web.lock -r requirements-dev.txt
COPY . .
COPY --from=frontend /src/static/dashboard ./static/dashboard
COPY --from=docs /src/docs/_site ./docs/_site
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS worker-dev
COPY requirements-worker.lock requirements-dev.txt ./
RUN pip install -r requirements-worker.lock -r requirements-dev.txt
COPY . .
CMD ["sh", "-c", "python manage.py createcachetable && python manage.py db_worker --queue-name default,scores"]
