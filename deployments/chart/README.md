# bgc-data-portal Helm chart

Canonical, single-source deployment for the BGC Data Portal. One chart renders
three targets; pick one by passing its values file (the base `values.yaml` is a
minimal skeleton and is **not** a usable target on its own):

| Target | Values | Where |
|--------|--------|-------|
| self-host / laptop | `values-laptop.yaml` (+ `values-selfhost.yaml` for the published quay images) | here (public) |
| cloud-dev | `envs/cloud-dev/values.yaml` | `mgnify-bgcs-deployer` (private) |
| cloud-prod | `envs/cloud-prod/values.yaml` | `mgnify-bgcs-deployer` (private) |

What the chart renders: `postgres` (StatefulSet, also the cache and the
django-tasks queue), `bgc-data-portal-django` (gunicorn / `runserver`, migrate
init-container), `bgc-data-portal-worker` (`manage.py db_worker`, mounts the
`/data` artifacts volume), the static NGINX + ingress on cloud targets, and
optional `tests.jobs` hooks. No Redis, RabbitMQ or Celery.

## Install paths

| Path | Command | Notes |
|------|---------|-------|
| Build from source (recommended) | `make selfhost` (app repo) or `scripts/selfhost-build.sh -h` | Builds the `web` + `worker` targets of `django/Dockerfile`, imports them into k3d, creates the Secret, installs with `values-laptop.yaml`. |
| Published OCI chart | `helm pull oci://quay.io/microbiome-informatics/bgc-data-portal-chart --untar` then `helm install bgc ./bgc-data-portal -f …/values-laptop.yaml -f …/values-selfhost.yaml -n bgc-local --create-namespace` | Needs the quay images/chart to be reachable. Pin with `--set django.image=…:vX --set worker.image=…-worker:vX`. |
| Dev loop | `make dev` (Skaffold on k3d) | Same chart; Skaffold's post-renderer swaps in the freshly built dev images. |
| Cloud dev / prod | `make -C deployments/cloud render-prod`, `verify-prod`, `secret-prod`, `deploy-prod KUBE_CONTEXT=<ctx> CHART_VERSION=<chart version>` | Targets live in the **monorepo** at `deployments/cloud/Makefile`; the per-env values and golden renders live in the `mgnify-bgcs-deployer` submodule. `deploy-prod` requires a published `CHART_VERSION`. |

The walkthrough (cluster, secret, access, snapshot load, teardown) is in the app
[`README.md`](../../README.md); the post-install `NOTES` print the access URL
and snapshot-load commands.

## Secret

The chart references a Secret named `bgc-data-portal-secret` but never
templates it. `make selfhost` and `make -C deployments/cloud secret-<env>`
create it; otherwise:

```bash
kubectl create secret generic bgc-data-portal-secret --from-env-file=my-secrets.env -n <ns>
```

Keys: `DJANGO_SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`DATABASE_URL` (pointing at the in-cluster `postgres` service). Non-secret
settings such as `NINJA_NUM_PROXIES` (defaults to `1`, required outside `DEBUG`)
go in `config.data`.

## Conventions

- Templates are thin skeletons; structurally-varying blocks (`env`, `command`,
  `volumes`, probes, `securityContext`, ingress rules) are passed through
  verbatim from values, so a target's values file fully describes its pods.
- Helm deep-merges maps but replaces lists — keep map-shaped, target-specific
  settings empty in `values.yaml` and declare them per target.
- Init-container images follow `django.image`, so one image override covers main
  + init containers; the worker is `worker.image`.
- Bump `version:` in `Chart.yaml` whenever the chart changes — that string is the
  published OCI tag (`publish-chart.yml`).
- `deployments/cloud/scripts/verify_parity.py` (monorepo) proves a cloud render
  matches its committed golden (`make -C deployments/cloud verify-<env>`).

## Links

- App developer guide: [`README.md`](../../README.md)
- Helm design notes, dev loop, OCI publishing, troubleshooting:
  `docs/runbooks/services/bgc_data_portal/deployment-helm.md` (monorepo)
- Prod SOP: `docs/runbooks/services/bgc_data_portal/production-deployment-cycle.md` (monorepo)
- Snapshots: `docs/runbooks/services/bgc_data_portal/data-snapshot.md` (monorepo)
