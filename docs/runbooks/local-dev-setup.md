# Local Dev Setup (kind + Skaffold)

This runbook gets you a production-faithful local environment using
[kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker) and
[Skaffold](https://skaffold.dev/). The dev image omits ML packages
(torch, esm, etc.) so first builds complete in ~3 min instead of ~20 min.

## Prerequisites

Install via Homebrew (macOS / Linux):

```bash
brew install kind kubectl skaffold make
# Docker Desktop or OrbStack must be running
```

Verify:

```bash
kind version      # >= 0.23
kubectl version   # >= 1.29
skaffold version  # >= 2.13
```

## First-time Setup

```bash
# 1. Create the kind cluster (exposes port 8080 on localhost)
make cluster-create

# 2. Copy secrets template and fill in values
#    The defaults work out-of-the-box for local dev
cp deployments/k8s-local/.env.local.example deployments/k8s-local/.env.local

# 3. Build dev image, create secrets, and deploy all services
make deploy-local
```

The first `make deploy-local` pulls base images and installs Python packages.
Subsequent runs use the Docker layer cache and are much faster.

## Active Development (hot-reload)

```bash
make dev
```

Skaffold watches for file changes and syncs `*.py`, `*.html`, `*.css`, `*.js`
directly into the running pod — no image rebuild needed. Django `runserver`
auto-reloads on `.py` changes. Celery restarts automatically via `watchmedo`.

## Accessing the App

| URL | Description |
|-----|-------------|
| `http://localhost:8080` | Django portal |
| `http://localhost:8080/api/docs` | Swagger UI |
| `http://localhost:8080/api/redoc` | ReDoc |
| `http://localhost:15672` | RabbitMQ management UI (guest / guest) |

> Port 8080 is mapped from container port 30080 via kind's `extraPortMappings`.

## Running Tests

```bash
# Unit tests (fast, no external services)
make test-unit

# Integration tests (requires running cluster)
make test-integration

# E2E Playwright tests (run outside cluster)
make test-e2e
```

## Useful Commands

```bash
make logs       # Tail Django logs
make shell      # bash shell inside Django pod
make db-shell   # psql inside postgres StatefulSet
```

## Teardown

```bash
make delete-local    # Remove Skaffold-managed resources
make cluster-delete  # Delete the kind cluster entirely
```

## Notes on ML Management Commands

`Dockerfile.dev` omits ML packages (torch, transformers, esm, biopython,
pyrodigal, pyhmmer, rdkit). Management commands that need them
(e.g. `backfill_protein_embeddings`) must be run using the full prod image:

```bash
docker run --rm -it \
  --env-file deployments/k8s-local/.env.local \
  quay.io/microbiome-informatics/bgc_dp_web_site:latest \
  python manage.py backfill_protein_embeddings
```
