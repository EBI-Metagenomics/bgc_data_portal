# CLAUDE.md — BGC Data Portal

Django 5 web portal and REST API for Biosynthetic Gene Clusters (BGCs) in MGnify.
`README.md` is the canonical developer guide; this file is the short version.

## Common Commands

Local dev runs on a k3d cluster through Skaffold (no docker-compose):

```bash
make dev                      # build dev images, deploy the chart, hot-reload at :8080
make test-unit                # pytest django/tests/unit (inside the django pod)
make test-integration         # pytest django/tests/integration
make test-e2e                 # Playwright specs against http://localhost:8080/dashboard
make shell                    # bash in the django pod
make logs-django / logs-worker
```

A fresh dev DB needs schema + data before the dashboard has anything to render:

```bash
make reset-db                 # rebuild the schema (DESTRUCTIVE, dev only)
make seed-real-data           # load staged ETL tarballs (STAGED_FILES_DIR)
make e2e-seed                 # build_integrated_bgcs
```

Running the suite outside the cluster: point `DATABASE_URL` at any Postgres 18,
set `DJANGO_SECRET_KEY` and `ALLOWED_HOSTS`, then `pytest -q` from the repo root
(`pyproject.toml` holds the pytest config).

### Code quality

```bash
ruff check . --fix
ruff format .
pre-commit run --all-files
```

### Management commands (run in a pod: `kubectl exec -n <ns> deploy/bgc-data-portal-worker -- python manage.py …`)

```bash
manage.py load_discovery_data <dir> [--truncate]   # staged ETL TSVs -> DB
manage.py build_integrated_bgcs                     # rebuild iBGCs (+ NPClassifier label union, stats)
manage.py load_npc_ontology                         # NPClassifier terms (idempotent; the loader runs it too)

# Clustering is an HPC handoff: export, run `bgc-cluster` (common-core) on HPC, import.
manage.py export_clustering_inputs --run-tag <tag>
manage.py import_clustering_results /data/clustering_artifacts/imports/<tag>.tgz
manage.py set_active_clustering_run --sha <previous_sha>   # rollback to a prior run
manage.py reclassify_bgcs --run <pk>                       # partial / non-primary iBGCs
manage.py recompute_all_scores
manage.py build_protein_search_index --rebuild|--append    # phmmer index (worker pod)
manage.py update_discovery_stats
```

## Architecture

```
django/
  bgc_data_portal/        # Settings, root URLs, template views (landing, about, docs, SPA host)
  discovery/              # The app (iBGC-first)
    models.py             # ORM models (IntegratedBgc, SourceBgcPrediction, ClusteringRun, …)
    api.py                # Django Ninja REST API (OpenAPI at /api/docs)
    api_schemas.py        # Pydantic schemas for API I/O
    tasks.py              # django-tasks background tasks
    services/             # Business logic
      clustering/         # iBGC similarity + scoring against the active ClusteringRun
        ibgc_scoring.py   # novelty, domain_novelty, partial projection
        similarity_on_demand.py  # Find-similar / architecture search from the scoring cache
        membership.py, adjacency.py, feature_weights.py, enrichment.py  # feature matrices (ADR 0003)
        integrated.py     # IntegratedBgc table builder
        reclassify.py     # KNN reclassification of non-primary iBGCs
      ingestion/          # Staged-TSV loader (load_discovery_data)
      asset_upload/       # "Load asset" tarball: parse, validate, project virtual iBGCs
      protein_search/     # phmmer-based sequence search
      query/              # Combined query criteria (domains, architecture, sequence)
      report.py           # Shortlist Report payload builder
  frontend/               # React + TypeScript (Vite) SPA, built into static/dashboard
  docs/                   # Quarto user docs served at /docs/
  tests/                  # unit/, integration/, e2e/playwright/
deployments/chart/        # The one Helm chart (laptop, self-host, cloud via deployer values)
```

## Key Patterns

**iBGC-first** — The dashboard surfaces `IntegratedBgc` rows, each consolidating
one or more `SourceBgcPrediction` detections. `is_partial=True` marks iBGCs whose
GCF / novelty were projected from top-K primary neighbours; `False` means the row
was clustered directly. There is no 2D layout; the Variables map is the only scatter.

**Composite similarity** — Each `ClusteringRun` records its `similarity_metric`
(ADR 0003): `cosine_idf_enrich` = `w_d · cos_w(domains) + w_a · cos_w(adjacency)`
with per-feature weights `idf ** idf_exponent × enrich` (defaults 0.6/0.4, 0.5), or
`dice` for older runs. Every consumer (novelty, Find similar, architecture search,
asset upload, partial projection) scores with the active run's metric and weights
from `<CLUSTERING_ARTIFACTS_DIR>/<sha[:12]>/scoring_cache/`.

**NPClassifier search** — SanntiS 1.0 predicts NPClassifier pathway / superclass;
MIBiG entries carry curated labels. The loader writes `SourceBgcNpcLabel`,
`build_integrated_bgcs` unions them into `IbgcNpcLabel`, and the `npc_terms` filter
(plus `npc_confident`) expands a term to its descendants over `common_core.npc`.

**Async search** — `POST /query/combined/` enqueues a django-tasks job (Postgres
`django-tasks-db` backend, `manage.py db_worker`); the UI polls
`/query/combined/status/{task_id}/scores/`. Sequence search uses pyhmmer phmmer.

**Shortlist Report** — Stateless. `POST /report/snapshot/` materialises the payload
in the cache under a deterministic `sha256(sorted ids)[:32]` token (24 h TTL);
`GET /report/{token}/` serves it. The shortlist holds up to 1,000 iBGCs.

**API access** — Endpoints in `/api/docs` are open and rate-limited per client IP.
UI-only endpoints (`include_in_schema=False`) accept same-origin browser traffic
only (`discovery/security.py`). There are no write endpoints.

## Stack

| Component | Technology |
|-----------|-----------|
| Web framework | Django 5 + Django Ninja |
| Database, cache, task queue | PostgreSQL 18 (DatabaseCache, django-tasks-db) |
| Background worker | `manage.py db_worker` |
| Production server | Gunicorn behind the k8s ingress |
| Frontend | React 18 + TypeScript + Vite + Tailwind, Plotly |
| Local dev | k3d + Skaffold + the Helm chart |
