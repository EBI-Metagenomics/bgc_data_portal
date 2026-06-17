FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    make \
    git \
    libxrender1 \
    libxext6 \
    libsm6 \
    curl \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ChemOnt ontology. The web pod needs it to build the hierarchical ChemOnt
# filter tree (/filters/chemont-classes/) and to expand a selected parent class
# to its descendants; without it both fall back to flat leaves. Baked in at
# build time (same source as the worker/ETL images) at the default path expected
# by common_core.chemont.ontology. ``/data/<subdir>`` volume mounts don't shadow
# this, so no PVC/mount is needed. Vendored in-repo (vendor/chemont/) rather than
# fetched from classyfire.wishartlab.com, which is frequently unreachable.
# ChemOnt is a static ontology (data-version 2.1, 2016), so it never goes stale.
RUN mkdir -p /data/chemont
COPY vendor/chemont/ChemOnt_2_1.obo /data/chemont/ChemOnt_2_1.obo
ENV CHEMONT_OBO_PATH=/data/chemont/ChemOnt_2_1.obo

WORKDIR /app
COPY requirements-web.lock .
RUN pip install --upgrade pip && pip install -r requirements-web.lock

COPY . .

# Build the React frontend (outputs to /app/static/dashboard/)
# Vite needs the externally-mounted base path baked into the bundle so chunk
# imports resolve through the production ingress prefix.
ARG VITE_BASE_PATH=/finn-srv/mgnify-bgcs/static/dashboard/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
WORKDIR /app/frontend
RUN npm install && npm run build
WORKDIR /app

EXPOSE 8000
ENV PYTHONUNBUFFERED=0

RUN python manage.py collectstatic --noinput || true

RUN chgrp -R 1347 /app && chmod -R g+w /app
