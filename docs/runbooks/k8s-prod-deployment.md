# k8s-prod Deployment

Deploy the BGC Data Portal to the EBI HL Kubernetes cluster (production namespace).

## When to Release

Release Please monitors commits on `main` and opens a release PR automatically when
it detects `feat:` or `fix:` commits. Merging that PR:
1. Bumps `version.txt` and `CHANGELOG.md`
2. Creates a GitHub Release and git tag (e.g. `v1.4.0`)

The production image build is triggered separately (see below).

## Building the Production Image

The full production image (includes biopython, pyhmmer, rdkit, etc.; torch
and ESM were removed when sequence search moved to phmmer) is built by
`.github/workflows/release.yml` when a commit message contains `"release portal"`.

To trigger manually from a release commit:

```bash
git commit --allow-empty -m "chore(portal): release portal v1.4.0"
git push
```

The workflow builds from `django/Dockerfile` (not `Dockerfile.dev`), runs
`collectstatic`, and pushes to:
`quay.io/microbiome-informatics/bgc_dp_web_site:<tag>`

## Secrets

> **The secret must exist in the namespace before running `make deploy-prod`.**

Secrets are stored in the `bgc-data-portal-secret` Kubernetes Secret in the
`bgc-data-portal-hl-prod` namespace. To create or rotate secrets:

```bash
# Edit the values in a local copy of the secrets template (never commit this file)
cp deployments/k8s-prod/secrets-template.yaml /tmp/bgc-prod-secret.yaml
# Fill in values, then apply
kubectl apply -f /tmp/bgc-prod-secret.yaml --context <prod-kube-context>
rm /tmp/bgc-prod-secret.yaml
```

## Deploying

```bash
# Build prod image, push to quay.io, apply k8s-prod manifests
KUBE_CONTEXT=<prod-kube-context> make deploy-prod
```

This runs `skaffold run -p prod` which applies `deployments/k8s-prod/ebi-wp-k8s-hl.yaml`
to namespace `bgc-data-portal-hl-prod`.

## Production URL

`https://www.ebi.ac.uk/finn-srv/mgnify-bgcs`

## Rollback

To roll back to a previous image tag:

```bash
# List recent image tags on quay.io, identify the previous good tag
# Update the image tag in deployments/k8s-prod/ebi-wp-k8s-hl.yaml, then:
kubectl apply -f deployments/k8s-prod/ebi-wp-k8s-hl.yaml \
  --context <prod-kube-context> -n bgc-data-portal-hl-prod

# Or remove all Skaffold-managed resources and redeploy with a specific tag:
KUBE_CONTEXT=<prod-kube-context> skaffold delete -p prod
KUBE_CONTEXT=<prod-kube-context> make deploy-prod
```

## Protein Search Index (phmmer)

The Discovery Dashboard "Protein Sequence" search runs `phmmer` against an
on-disk reference DB at `/data/protein_search`, mounted from the
`bgc-hf-cache-claim` PVC (repurposed from the former HuggingFace/ESM model
cache).

**Build it once after the first rollout** that includes the phmmer-based
search. The PVC persists across re-deploys, so subsequent rollouts reuse the
populated FASTA — there is nothing to do on routine deploys.

### One-time bootstrap

Run on the **celery pod**:

```bash
kubectl exec -n bgc-data-portal-hl-prod deploy/bgc-data-portal-celery \
  --context <prod-kube-context> -- \
  python manage.py build_protein_search_index --rebuild
```

At 10M proteins this takes ~5–10 minutes; tail `kubectl logs` on the celery
deployment to watch progress.

> If the PVC carries leftover `huggingface/` data from before the repurpose,
> wipe it once: `kubectl exec ... deploy/bgc-data-portal-celery -- rm -rf /data/protein_search/huggingface`.

### Steady state

`load_discovery_data` auto-enqueues an index update at the end of every
ingest — `--truncate` triggers a rebuild, otherwise the new proteins are
appended. Celery workers detect the new `VERSION` stamp and reload their
in-memory block on the next query. **Nothing to wire per-deploy.**

Pass `--skip-protein-index` to defer the update when loading multi-archive
batches; then run `python manage.py build_protein_search_index --append`
once at the end.

### Resourcing

Celery workers run `--concurrency=1` so a single phmmer DB is resident per
pod; scale horizontally via replicas. At the 10M-protein scale, each worker
pod needs roughly 5 GB requested / 8 GB limit.

## Post-Deploy Verification

```bash
# Smoke test
curl -I https://www.ebi.ac.uk/finn-srv/mgnify-bgcs/api/docs

# View prod logs
kubectl logs -f -n bgc-data-portal-hl-prod deploy/bgc-data-portal-django \
  --context <prod-kube-context>
```

### Running tests in prod

Only unit tests (which require no DB access) should be run against the production pod.
Integration tests write to the database and must never be run in prod.

```bash
kubectl exec -n bgc-data-portal-hl-prod deploy/bgc-data-portal-django \
  --context <prod-kube-context> -- pytest tests/unit/ -q
```

### Seeding in prod

**Do not run `seed_data` against production.** The command inserts synthetic rows that
would pollute real data. Use it only in local KIND or k8s-dev environments.

To populate prod with real data, use the ETL pipeline and `load_assembly_staged_tsvs`
management command as described in the ETL runbook.
