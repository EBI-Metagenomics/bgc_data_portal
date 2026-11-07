# MGnify BGC Data Portal

A web portal and REST API for exploring **biosynthetic gene clusters (BGCs)**
predicted across MGnify metagenomic datasets. The portal harmonises outputs from
multiple detection tools (antiSMASH, GECCO, SanntiS) into a single **integrated
BGC (iBGC)** catalogue you can search, cluster, visualise, and download.

Developed by the [MGnify](https://www.ebi.ac.uk/metagenomics) team at EMBL-EBI as
part of the EUREMAP project.

- **Discovery Platform:** served at `/dashboard/`
- **Discovery Platform docs:** pages at `/docs/`
- **API docs:** Swagger UI at `/api/docs`
---

## What you can do

- Browse the **iBGC-first** dashboard — each iBGC consolidates one or more
  source predictions, grouped into gene-cluster families (GCFs) and plotted on
  the Variables map.
- **Search** the catalogue: faceted metadata filters (class, completeness,
  detector, taxonomy, biome, natural-product class) and advanced chips for
  protein-domain and **sequence search** (phmmer-based protein similarity).
- Inspect an iBGC's regions, domains, NPClassifier labels, novelty scores, and
  nearest neighbours.
- **Download** a BGC as GBK / FNA / FAA / JSON, or export result sets as TSV.
- Build a **shortlist report** from selected iBGCs (shareable snapshot token).
- Drive everything programmatically through the Django Ninja REST API.

---

## Run your own instance (self-host)

You need a single-node Kubernetes cluster and a container runtime
(Docker / Colima / Podman). [k3d](https://k3d.io) is the lightest option:

```bash
k3d cluster create bgc-local -p "8080:30080@server:0"   # NodePort → host :8080
kubectl config use-context k3d-bgc-local
```

### Install — build from source (recommended, no registry needed)

The app images build entirely from public base images, so you never touch a
private registry. One command builds the `web` and `worker` targets of
`django/Dockerfile`, imports them into k3d, and installs the Helm chart:

```bash
make selfhost
#  or, for cluster/namespace/tag/secret options:
scripts/selfhost-build.sh -h
```

This installs the chart in `deployments/chart/` with `values-laptop.yaml` and the
locally built image names, and creates the `bgc-data-portal-secret` for you.

### Install — from the published OCI chart (alternative)

If `quay.io/microbiome-informatics` (chart + images) is reachable, you can skip
the build. Create the secret first (see below), then:

```bash
helm pull oci://quay.io/microbiome-informatics/bgc-data-portal-chart --untar
helm install bgc ./bgc-data-portal \
  -f ./bgc-data-portal/values-laptop.yaml \
  -f ./bgc-data-portal/values-selfhost.yaml \
  -n bgc-local --create-namespace
```

`values-selfhost.yaml` selects the published quay images; pin a version with
`--set django.image=…:vX --set worker.image=…-worker:vX` (init-container images
follow `django.image`).

### Secret

`make selfhost` creates the secret automatically. For the OCI path (or any manual
install) create it first — a secret named `bgc-data-portal-secret` with these
keys (defaults are fine for a private instance):

```bash
kubectl create namespace bgc-local
kubectl create secret generic bgc-data-portal-secret \
  --from-env-file=my-secrets.env -n bgc-local
```

```
DJANGO_SECRET_KEY
POSTGRES_USER          POSTGRES_PASSWORD      POSTGRES_DB
DATABASE_URL
```

Point `DATABASE_URL` at the in-cluster `postgres` service — it also backs the
cache (DatabaseCache) and the background-task queue (django-tasks-db). No Redis
or RabbitMQ to configure. Outside `DEBUG`, `NINJA_NUM_PROXIES` must be set to
the number of reverse proxies in front of Django (the chart defaults it to `1`).

### Access

```bash
kubectl -n bgc-local rollout status deploy/bgc-data-portal-django
```

Open **<http://localhost:8080/dashboard/>** (with the k3d NodePort mapping above;
otherwise `kubectl -n bgc-local port-forward svc/bgc-data-portal-django 8080:80`).

### Load data (a fresh instance is empty)

The images ship no reference data. Load a published snapshot (DB dump +
clustering artifacts + protein-search index) to get a working catalogue.
Snapshots live at
`https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_bgcs/snapshots/`
(`latest.txt` names the newest compatible bundle):

```bash
NS=bgc-local
curl -fSL "https://ftp.ebi.ac.uk/.../bgc-portal-snapshot-<ver>.tgz" -o snapshot.tgz
mkdir -p snap && tar -xzf snapshot.tgz -C snap

# DB (POSTGRES_USER/DB are the values you put in the secret)
kubectl -n "$NS" exec -i postgres-0 -- \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < snap/db.dump

# clustering artifacts + protein-search index (the worker pod mounts /data), then refresh stats
WK=$(kubectl -n "$NS" get pod -l app=bgc-data-portal-worker -o name | head -1)
kubectl -n "$NS" exec -i "$WK" -- tar -C /data -xzf - < snap/artifacts.tgz
kubectl -n "$NS" exec "$WK" -- python manage.py update_discovery_stats
```

No further network access is needed afterwards — suitable for an air-gapped HPC
or laptop.

> Chart reference (targets, values conventions, secret keys):
> [`deployments/chart/README.md`](./deployments/chart/README.md).

### Teardown

```bash
helm uninstall bgc -n bgc-local
k3d cluster delete bgc-local
```

---

## Develop

Local development runs the **same Helm chart** on a k3d cluster, with
**Skaffold** building the dev images and hot-reloading `django/`. There is no
docker-compose. You need `k3d`, `kubectl`, `skaffold`, and **Helm v3**
(`brew install helm@3` — Skaffold is incompatible with Helm v4).

```bash
make dev          # build dev images, deploy the chart to k3d, watch django/ for changes
make dev-clean    # tear the Skaffold release down
```

Skaffold forwards `django:80` → `localhost:8080`; the dashboard is at
`/dashboard/`. Everything runs in two pods: `bgc-data-portal-django` (web) and
`bgc-data-portal-worker` (`manage.py db_worker`, plus the science stack —
pyhmmer, numpy/scipy — that the web image does not carry). Make targets wrap
`kubectl exec`:

```bash
make test-unit            # pytest tests/unit/        (TEST_POD=bgc-data-portal-worker for the science tests)
make test-integration     # pytest tests/integration/
make shell                # shell into the django pod
make logs-django          # tail logs (also: make logs-worker)
make db-shell             # psql into postgres
make clear-cache          # cache.clear() on the DatabaseCache
```

### Images

One multi-stage `django/Dockerfile` builds every image. Targets:

| Target | Used for |
|--------|----------|
| `web` | production web pod (gunicorn; `requirements-web.lock`) |
| `worker` | production `db_worker` pod (`requirements-worker.lock`) |
| `web-dev` | web + `requirements-dev.txt`, `runserver` with autoreload (Skaffold) |
| `worker-dev` | worker + dev tools, `db_worker --reload` (Skaffold) |

A `node` stage builds the frontend bundle into `static/dashboard` for the `web*`
targets. Lockfiles are compiled with `make lock` (uv, linux/amd64, py3.12) and
checked by `make lock-check` (CI runs it): every exact pin in
`requirements-*.txt` must appear unchanged in its `.lock`.

### Tests outside the cluster

`pyproject.toml` holds the pytest config (`pythonpath = django`, `testpaths =
django/tests`). Point the suite at any Postgres 18 and run it from the repo root:

```bash
export DATABASE_URL=postgres://user:pass@localhost:5432/bgc
export DJANGO_SECRET_KEY=dev ALLOWED_HOSTS=localhost
pytest -q                                  # unit + integration
pytest -q django/tests/unit                # just the unit suite
```

### Lint

```bash
ruff check . --fix
ruff format .
pre-commit run --all-files                 # runs the same hooks
```

### Frontend

The dashboard is a React + TypeScript SPA under `django/frontend/` (Vite,
Tailwind, Plotly). `npm run build` (`tsc -b && vite build`) writes the bundle to
`django/static/dashboard/`, which Django serves at `/dashboard/`; `npm run lint`
is `tsc --noEmit`. The Dockerfile's node stage runs the same build, so you only
build by hand when iterating on the SPA.

```bash
cd django/frontend
npm ci
npm run lint
npm run build
```

`VITE_BASE_PATH` is baked into the bundle as the asset prefix. Local builds and
Skaffold use the default `/static/dashboard/`; it only matters for release
images, where the Dockerfile sets the production ingress prefix
(`/finn-srv/mgnify-bgcs/static/dashboard/`).

### Seed a dev database

A fresh DB needs schema + data before there's anything to render:

```bash
make reset-db                              # rebuild the v2 schema (DESTRUCTIVE, dev only)
STAGED_FILES_DIR=/path/to/staged \
  make seed-real-data                      # load staged ETL tarballs (load_discovery_data)
make e2e-seed                              # build_integrated_bgcs (worker pod)
make build-protein-index                   # build the sequence-search index (worker pod)
```

A GCF hierarchy additionally needs a clustering run imported (see **Data
maintenance**).

### End-to-end tests

Playwright specs run **outside** the cluster against the forwarded port (needs
`pip install pytest-playwright` + `playwright install chromium` once):

```bash
make test-e2e             # pytest django/tests/e2e/playwright --e2e-v2-base-url $E2E_URL
make test-e2e E2E_URL=https://example.org/dashboard PYTEST=.venv/bin/pytest
```

### Render the user docs

The in-app docs are Quarto pages served at `/docs/`:

```bash
cd django/docs && quarto render
```

---

## Data maintenance

Management commands run in a pod — the worker pod for anything that needs the
science stack or the `/data` artifacts mount:

```bash
kubectl exec -n <ns> deploy/bgc-data-portal-worker -- python manage.py <command>
```

| Command | What it does |
|---------|--------------|
| `load_discovery_data --data-dir <dir> [--truncate]` | Load staged ETL TSVs (assemblies, contigs, source predictions, CDS, domains, NPClassifier labels); enqueues the protein-index update and stats refresh. |
| `build_integrated_bgcs` | Rebuild the iBGC table from source predictions (+ per-iBGC NPClassifier label union). |
| `load_npc_ontology` | Upsert the NPClassifier terms from `common_core.npc` (idempotent; the loader runs it too). |
| `export_clustering_inputs --run-tag <tag>` | DB → `in.tgz` (feature matrices + ADR 0003 weights) for the HPC handoff. |
| `import_clustering_results <tag>.tgz` | Load a `bgc-cluster` output tarball (GCF hierarchy, scores, partial projection) and activate the run. |
| `set_active_clustering_run --sha <sha>` | Roll back to a previously imported run. |
| `reclassify_bgcs --run <pk>` | KNN re-projection of partial / non-primary iBGCs onto the run. |
| `recompute_all_scores` | Recompute novelty / domain novelty against the active run. |
| `build_protein_search_index --rebuild \| --append` | Build or extend the phmmer index (`make build-protein-index` / `update-protein-index`). |
| `update_discovery_stats` | Refresh the cached dashboard counts. |
| `backfill_go_slim` | Refresh `ContigDomain.go_slim` after regenerating the GO-slim map (below). |

Clustering itself is an HPC handoff — `export_clustering_inputs` →
`bgc-cluster run` (from `mgnify-bgcs-common-core`) on SLURM →
`import_clustering_results`. The monorepo runbook `clustering-compute.md` has
the SLURM wrappers and sizing.

### GO-slim map

The Discovery domain panel and Protein Information card colour CDS by GO-slim
term. The mapping `GO id → slim term names` lives at
`django/discovery/services/data/go_slim_map.json` and is regenerated locally
with a standalone script (no Django needed):

```bash
pip install goatools
python scripts/refresh_go_slim_map.py --download
```

`--download` fetches `go-basic.obo` + `goslim_metagenomics.obo` into
`/tmp/go_obo`. Run `--help` for the other knobs (`--slim`, `--aspect`,
`--obo-dir`, `--output`). After regenerating, commit the JSON and run
`python manage.py backfill_go_slim` to refresh existing `go_slim` rows.

---

## Architecture

| Component          | Technology                                          |
|--------------------|-----------------------------------------------------|
| Web framework      | Django 5 + Django Ninja (OpenAPI)                   |
| Database           | PostgreSQL 18                                       |
| Cache              | PostgreSQL (Django DatabaseCache)                   |
| Background tasks   | django-tasks + django-tasks-db (`manage.py db_worker`) |
| Frontend           | React 18 + TypeScript + Vite + Tailwind, Plotly     |
| Production server  | Gunicorn behind the Kubernetes ingress              |
| Packaging / deploy | One Helm chart → k3d (self-host/dev) or cloud k8s  |

The catalogue is **iBGC-first**: `IntegratedBgc` rows are the primary unit
everywhere. Similarity is the **weighted cosine** of
[ADR 0003](https://github.com/EBI-Metagenomics/mgnify_bgcs_v2/blob/main/docs/architecture/adr/0003-ibgc-similarity-weighted-cosine.md):
each protein domain / adjacency pair is weighted by `idf ** 0.5 × enrichment`
(rarity across taxa × enrichment in BGC cores over flanks), composited as
`0.6 · cos(domains) + 0.4 · cos(adjacency)`; older runs record `dice`. That
feeds a KNN → hierarchical Leiden clustering that assigns iBGCs to
gene-cluster families and computes novelty scores. The clustering runs as an
HPC handoff (above). NPClassifier labels (SanntiS 1.0 predictions, MIBiG
curation) and the InterProScan 6 domain vocabulary follow
[ADR 0004](https://github.com/EBI-Metagenomics/mgnify_bgcs_v2/blob/main/docs/architecture/adr/0004-sanntis-v1-ips6-npclassifier.md).

```
django/
  bgc_data_portal/    # project settings, root URLs, SPA + docs views
  discovery/          # the app (iBGC-first): models, api, tasks, services/
  frontend/           # React + TypeScript SPA (Vite) → static/dashboard
  docs/               # in-app Quarto docs (served at /docs/)
  tests/              # unit / integration / e2e
  Dockerfile          # web, worker, web-dev, worker-dev targets
deployments/chart/    # Helm chart — single source of truth for all deploys
scripts/              # selfhost-build.sh, seed-real-data.sh, refresh_go_slim_map.py, lock_check.py
```

---

## API

The REST API is served under `/api/`, with interactive docs at **`/api/docs`**.
Discovery endpoints live under `/api/discovery/` (iBGC search, filters, GCFs,
reports, downloads).

- **Async search** — `POST /api/discovery/query/combined/` returns a
  `task_id`; poll `/query/combined/status/{task_id}/scores/` for results
  (django-tasks, run by `manage.py db_worker`).
- **Auth** — there are no write endpoints. UI-only endpoints accept same-origin
  browser traffic only (see `discovery/security.py`); the documented endpoints
  at `/api/docs` are open and rate-limited per client IP.

---

## Deployment

All environments render from **one Helm chart** (`deployments/chart/`): the
laptop / self-host targets use `values-laptop.yaml` (+ `values-selfhost.yaml`),
while cloud dev/prod values live in the private `mgnify-bgcs-deployer` repo
(consumed as a submodule of the `mgnify_bgcs_v2` monorepo, with the deploy
automation in that monorepo at `deployments/cloud/`, run as
`make -C deployments/cloud <target>`). Images publish to
`quay.io/microbiome-informatics` and the chart to
`oci://quay.io/microbiome-informatics/bgc-data-portal-chart` via GitHub
Actions. Versioning is automated by Release Please from
[Conventional Commits](https://www.conventionalcommits.org/).

Chart details and conventions: [`deployments/chart/README.md`](./deployments/chart/README.md).

---

## Funding

Part of the EUREMAP project, funded by the European Union under
HORIZON-INFRA-2023-DEV-01-04 (Grant No. 101131663).

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
