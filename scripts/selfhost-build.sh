#!/usr/bin/env bash
# =============================================================================
# Self-host the BGC Data Portal by BUILDING THE IMAGES FROM SOURCE — no access
# to a private image registry required. The app images build from the public
# base images in django/Dockerfile* (python:3.12-slim) and db init; the backing
# services (postgres/redis/rabbitmq) use public images too.
#
# It builds the prod images, imports them into a local k3d cluster, and installs
# the SAME canonical Helm chart used in the cloud (deployments/chart) — so there
# is no second deployment definition to drift.
#
# Usage:
#   scripts/selfhost-build.sh [-c cluster] [-n namespace] [-t tag] [-e secrets.env]
#
# Prereqs: docker, k3d, kubectl, helm (v3 OR v4 — plain `helm install` is fine on
# either; only the Skaffold dev loop needs v3). The cluster is created if missing.
# =============================================================================
set -euo pipefail

CLUSTER=bgc-local
NS=bgc-local
TAG=selfhost
SECRET_ENV=deployments/.env.local.example
CHART=deployments/chart

while getopts "c:n:t:e:h" o; do case "$o" in
  c) CLUSTER=$OPTARG ;;
  n) NS=$OPTARG ;;
  t) TAG=$OPTARG ;;
  e) SECRET_ENV=$OPTARG ;;
  h) sed -n '2,18p' "$0"; exit 0 ;;
  *) exit 2 ;;
esac; done

for bin in docker k3d kubectl helm; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR: '$bin' not found on PATH"; exit 1; }
done

DJANGO_IMG="bgc-data-portal-django:${TAG}"
WORKER_IMG="bgc-data-portal-django-worker:${TAG}"
KCTX="k3d-${CLUSTER}"

echo ">> [1/5] Build images from source (public base images only)"
docker build -t "$DJANGO_IMG" -f django/Dockerfile        django
docker build -t "$WORKER_IMG" -f django/Dockerfile.worker django

echo ">> [2/5] Ensure k3d cluster '${CLUSTER}' (NodePort 30080 -> host :8080)"
if ! k3d cluster list "$CLUSTER" >/dev/null 2>&1; then
  k3d cluster create "$CLUSTER" -p "8080:30080@server:0"
fi

echo ">> [3/5] Import the built images into k3d (no registry push)"
k3d image import "$DJANGO_IMG" "$WORKER_IMG" -c "$CLUSTER"

echo ">> [4/5] Namespace + Secret (from ${SECRET_ENV})"
kubectl --context "$KCTX" create namespace "$NS" \
  --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -
kubectl --context "$KCTX" create secret generic bgc-data-portal-secret \
  --from-env-file="$SECRET_ENV" -n "$NS" \
  --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -

echo ">> [5/5] helm upgrade --install (canonical chart, locally-built images)"
# Plain `helm install` works on Helm v3 or v4 (the Skaffold post-renderer issue
# does not apply here). Override with HELM=/path/to/helm if needed.
HELM="${HELM:-helm}"
"$HELM" --kube-context "$KCTX" upgrade --install bgc "$CHART" \
  -f "$CHART/values-laptop.yaml" \
  --set django.image="$DJANGO_IMG" --set django.imagePullPolicy=IfNotPresent \
  --set celery.image="$WORKER_IMG" --set celery.imagePullPolicy=IfNotPresent \
  --namespace "$NS"

cat <<EOF

>> Done. The pods build from your source — nothing was pulled from a registry.
   kubectl -n ${NS} rollout status deploy/bgc-data-portal-django
   open http://localhost:8080/dashboard/

   A fresh instance is EMPTY; load a data snapshot — see
   docs/runbooks/services/bgc_data_portal/data-snapshot.md
EOF
