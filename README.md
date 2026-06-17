# MGnify BGC Data Portal

A web portal and REST API for exploring **biosynthetic gene clusters (BGCs)**
predicted across MGnify metagenomic datasets. The portal harmonises outputs from
multiple detection tools (antiSMASH, GECCO, SanntiS) into a single **integrated
BGC (iBGC)** catalogue you can search, cluster, visualise, and download.

Developed by the [MGnify](https://www.ebi.ac.uk/metagenomics) team at EMBL-EBI as
part of the EUREMAP project.

- **Discovery Platform:** served at `/dashboard/`
- **Discovery Platform docs:** pages at `/docs`
- **API docs:** Swagger UI at `/api/docs`
---

## What you can do

- Browse the **iBGC-first** dashboard — each iBGC consolidates one or more
  source predictions, placed on a similarity map of gene-cluster families (GCFs).
- **Search** the catalogue: faceted metadata filters (class, completeness,
  detector, domains) and **sequence search** (phmmer-based protein similarity).
- Inspect an iBGC's regions, domains, novelty scores, and nearest neighbours.
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
private registry. One command builds the images, imports them into k3d, and
installs the Helm chart:

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
`--set django.image=…:vX --set worker.image=…_worker:vX`.

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
DJANGO_SECRET_KEY      ADMIN_API_TOKEN        PROJECT_USER_TOKEN
POSTGRES_USER          POSTGRES_PASSWORD      POSTGRES_DB
DATABASE_URL
```

Point `DATABASE_URL` at the in-cluster `postgres` service — it now also backs the
cache (DatabaseCache) and the background-task queue (django-tasks-db). No Redis
or RabbitMQ to configure.

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

# clustering artifacts + protein-search index, then refresh stats
DJ=$(kubectl -n "$NS" get pod -l app=bgc-data-portal-django -o name | head -1)
kubectl -n "$NS" exec -i "$DJ" -- tar -C /data -xzf - < snap/artifacts.tgz
kubectl -n "$NS" exec "$DJ" -- python manage.py update_discovery_stats
```

No further network access is needed afterwards — suitable for an air-gapped HPC
or laptop.

> Full chart reference (all install paths, cloud targets, and conventions):
> [`deployments/chart/README.md`](./deployments/chart/README.md).

### Teardown

```bash
helm uninstall bgc -n bgc-local
k3d cluster delete bgc-local
```

---

## Develop

The dev loop runs the same chart on k3d with **Skaffold** hot-reload. You need
`k3d`, `kubectl`, `skaffold`, and **Helm v3** (`brew install helm@3` — Skaffold is
incompatible with Helm v4).

```bash
make dev          # build, deploy to k3d, watch django/ for changes
```

Skaffold forwards `django:80` → `localhost:8080`; the dashboard is at
`/dashboard/`. Run commands and tests inside the cluster via Make targets (they
wrap `kubectl exec`):

```bash
make test-unit            # pytest tests/unit/
make test-integration     # pytest tests/integration/
make shell                # shell into the django pod
make logs-django          # tail logs
```

### Seed a dev database

A fresh DB needs schema + data before there's anything to render:

```bash
make reset-db                              # rebuild the v2 schema (DESTRUCTIVE, dev only)
STAGED_FILES_DIR=/path/to/staged \
  make seed-real-data                      # load raw discovery data
make build-protein-index                   # build the sequence-search index
```

### End-to-end tests

Playwright specs run **outside** the cluster against the forwarded port (needs
`playwright install chromium` once):

```bash
make e2e-seed             # build iBGCs + a clustering run from seeded data
make test-e2e             # run the browser suite
```

---

## Architecture

| Component          | Technology                                          |
|--------------------|-----------------------------------------------------|
| Web framework      | Django 5 + Django Ninja (OpenAPI)                   |
| Database           | PostgreSQL + pgvector                               |
| Cache              | PostgreSQL (Django DatabaseCache)                   |
| Background tasks   | django-tasks + django-tasks-db (`db_worker`)        |
| Production server  | Gunicorn (static served by NGINX in Kubernetes)    |
| Packaging / deploy | One Helm chart → k3d (self-host/dev) or cloud k8s  |

The catalogue is **iBGC-first**: `IntegratedBGC` rows are the primary unit
everywhere. Similarity uses a **composite Sørensen–Dice** score over shared
protein domains and adjacency pairs, feeding a KNN → hierarchical Leiden
clustering pipeline that assigns iBGCs to gene-cluster families and computes
novelty scores. Heavy clustering runs as an HPC handoff in production.

```
django/
  bgc_data_portal/    # project settings, root URLs, SPA + docs views
  discovery/          # v2 Discovery app (iBGC-first): models, api, tasks, services/
  mgnify_bgcs/        # legacy app (pre-v2, being retired)
  tests/              # unit / integration / e2e
db/                   # Postgres (pgvector) init
deployments/chart/    # Helm chart — single source of truth for all deploys
docs/                 # in-app Quarto docs
```

---

## API

The REST API is served under `/api/`, with interactive docs at **`/api/docs`**.
Discovery endpoints live under `/api/discovery/` (iBGC search, clustering,
reports, downloads).

- **Async search** — search endpoints return `202` with a `task_id`; poll the
  job-status endpoint for results (Celery-backed).
- **Auth** — admin DB-operation endpoints require
  `Authorization: Bearer <ADMIN_API_TOKEN>`; ingestion requires
  `Authorization: Bearer <PROJECT_USER_TOKEN>`.

---

## Deployment

All environments render from **one Helm chart** (`deployments/chart/`): the
laptop / self-host targets use `values-laptop.yaml` (+ `values-selfhost.yaml`),
while cloud dev/prod values live in the private `mgnify-bgcs-deployer` repo
(consumed as a submodule of the `mgnify_bgcs_v2` monorepo, with the deploy
automation in that monorepo at `deployments/cloud/`). Images publish to `quay.io/microbiome-informatics`
and the chart to `oci://quay.io/microbiome-informatics/bgc-data-portal-chart`
via GitHub Actions. Versioning is automated by Release Please from
[Conventional Commits](https://www.conventionalcommits.org/).

Chart details and conventions: [`deployments/chart/README.md`](./deployments/chart/README.md).

---

## Funding

Part of the EUREMAP project, funded by the European Union under
HORIZON-INFRA-2023-DEV-01-04 (Grant No. 101131663).

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
