# bgc-data-portal Helm chart

Canonical, single-source deployment for the BGC Data Portal. One chart renders
three targets; pick one by passing its values file (the base `values.yaml` is a
minimal skeleton and is **not** a usable target on its own):

| Target | Values | Where |
|--------|--------|-------|
| self-host / laptop | `values-laptop.yaml` (+ `values-selfhost.yaml` for public images) | here (public) |
| cloud-dev | `envs/cloud-dev/values.yaml` | `mgnify-bgcs-deployer` (private) |
| cloud-prod | `envs/cloud-prod/values.yaml` | `mgnify-bgcs-deployer` (private) |

## Self-hosting

Two ways in, depending on whether you can reach the image registry:

### A. Build from source — no registry needed (recommended)

The app images build entirely from public base images (`python:3.12-slim`,
`pgvector/pgvector`, …), so you never touch a private registry. From a checkout
of the app repo:

```bash
make selfhost                 # build prod images → import into k3d → helm install
#  or:  scripts/selfhost-build.sh -h     (cluster/namespace/tag/secret options)
```

It builds `django/Dockerfile` + `Dockerfile.worker`, imports them into a local
k3d cluster, and installs this chart with `values-laptop.yaml` + the built-image
names (init-container images follow `django.image`, so one override covers all).
No second deployment definition — same chart as the cloud.

### B. From the published OCI chart — needs the registry to be public

Only if `quay.io/microbiome-informatics` (images + `charts/`) is public:

```bash
helm pull oci://quay.io/microbiome-informatics/bgc-data-portal-chart --untar
helm install bgc ./bgc-data-portal \
  -f ./bgc-data-portal/values-laptop.yaml \
  -f ./bgc-data-portal/values-selfhost.yaml \
  --namespace bgc-local --create-namespace
```

`values-selfhost.yaml` selects the published quay images; override the tag with
`--set django.image=…:vX --set celery.image=…_worker:vX` to pin a version.

### Secret (path B / manual)

`make selfhost` (path A) creates the Secret for you from the env file. For path B
(or any manual install) a Secret named `bgc-data-portal-secret` must exist first
(DB creds, tokens, broker/cache URLs). The chart's `values-laptop.yaml` header
lists the keys; the defaults work for a private instance:

```bash
kubectl create namespace bgc-local
kubectl create secret generic bgc-data-portal-secret \
  --from-env-file=my-secrets.env -n bgc-local      # see the key list below
```

Keys: `DJANGO_SECRET_KEY ADMIN_API_TOKEN PROJECT_USER_TOKEN POSTGRES_USER
POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL CELERY_BROKER_URL
CELERY_RESULT_BACKEND DJANGO_CACHE_BACKEND` (with `DATABASE_URL` pointing at the
in-cluster `postgres` service, the broker at `rabbitmq`, cache/result at `redis`).

The post-install `NOTES` print the access URL and snapshot-load commands.

### Access

```bash
kubectl -n bgc-local rollout status deploy/bgc-data-portal-django
kubectl -n bgc-local port-forward svc/bgc-data-portal-django 8080:80
# → http://localhost:8080/dashboard/
```

### Load data (a fresh instance is empty)

Snapshots are published at
`https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_bgcs/snapshots/`
(`latest.txt` names the newest compatible bundle). To load one offline:

```bash
NS=bgc-local
curl -fSL "https://ftp.ebi.ac.uk/.../bgc-portal-snapshot-<ver>.tgz" -o snapshot.tgz
mkdir -p snap && tar -xzf snapshot.tgz -C snap

# DB (POSTGRES_USER/DB are the values you put in the Secret)
kubectl -n "$NS" exec -i postgres-0 -- \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < snap/db.dump

# clustering artifacts + protein-search index
DJ=$(kubectl -n "$NS" get pod -l app=bgc-data-portal-django -o name | head -1)
kubectl -n "$NS" exec -i "$DJ" -- tar -C /data -xzf - < snap/artifacts.tgz
kubectl -n "$NS" exec "$DJ" -- python manage.py update_discovery_stats
```

No further network access is needed afterwards — suitable for an air-gapped HPC
or laptop. (Producing/publishing a snapshot is an operator task; see the internal
`data-snapshot.md` runbook.)

### Substrate

Any single-node Kubernetes works. [k3d](https://k3d.io) is the lightest:
`k3d cluster create bgc-local -p "8080:30080@server:0"` exposes the NodePort on
host `:8080` directly (no port-forward needed).

## Cloud (operators)

```bash
# from the private mgnify-bgcs-deployer repo
make render-prod && make verify-prod && make deploy-prod KUBE_CONTEXT=<ctx>
```

Design notes, the dev (k3d) loop, OCI publishing, and troubleshooting live in
`docs/runbooks/services/bgc_data_portal/deployment-helm.md` (internal).

## Conventions

- Templates are thin skeletons; structurally-varying blocks (`env`, `command`,
  `volumes`, probes, `securityContext`, ingress rules) are passed through
  verbatim from values, so a target's values file fully describes its pods.
- Helm deep-merges maps but replaces lists — keep map-shaped, target-specific
  settings empty in `values.yaml` and declare them per target.
- Init-container images follow `django.image`, so one image override covers main
  + init containers.
- `scripts/verify_parity.py` (deployer repo) proves a render matches its golden.
