.PHONY: cluster-create cluster-delete create-local-namespace create-local-secrets \
        dev dev-full dev-clean dev-preflight deploy-local delete-local deploy-dev deploy-prod \
        test-unit test-integration test-e2e logs shell db-shell validate-secrets \
        clear-cache-redis clear-cache-celery clear-cache-django clear-cache \
        seed-real-data \
        build-protein-index update-protein-index \
        clean-images tidy nuke \
        workspace-enter workspace-login workspace-claude workspace-sync-in workspace-sync-out \
        workspace-patch workspace-apply-patch workspace-set-api-key workspace-restart

ENV_FILE := deployments/k8s-local/.env.local
STAGED_FILES_DIR := ../../.SCRATCH/STAGED_FILES_SAMPLES

# ── Secrets validation ─────────────────────────────────────────────────────────
REQUIRED_VARS := DJANGO_SECRET_KEY DATABASE_URL POSTGRES_USER POSTGRES_PASSWORD \
                 POSTGRES_DB CELERY_BROKER_URL CELERY_RESULT_BACKEND DJANGO_CACHE_BACKEND

validate-secrets:
	@test -f $(ENV_FILE) || \
	  (echo "INFO: $(ENV_FILE) not found, copying from example..." && \
	   cp $(ENV_FILE).example $(ENV_FILE))
	@for var in $(REQUIRED_VARS); do \
	    grep -q "^$$var=" $(ENV_FILE) || \
	      (echo "ERROR: $$var is missing in $(ENV_FILE)" && exit 1); \
	done
	@echo "Secrets OK"

# ── Cluster lifecycle ──────────────────────────────────────────────────────────
cluster-create:
	kind create cluster --config deployments/k8s-local/kind-cluster.yaml

cluster-delete:
	kind delete cluster --name bgc-local

# ── Secrets ───────────────────────────────────────────────────────────────────
# Wait for any in-progress namespace deletion before re-applying. Without this,
# a fast-retry of `make dev` after a previous teardown hits:
#   "namespace bgc-local … is forbidden … is being terminated"
create-local-namespace:
	@if kubectl get ns bgc-local -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Terminating; then \
	  echo "Namespace bgc-local is Terminating; waiting up to 120s for cleanup..."; \
	  kubectl wait --for=delete ns/bgc-local --timeout=120s || \
	    (echo "ERROR: bgc-local stuck Terminating. Inspect: kubectl get ns bgc-local -o yaml" && exit 1); \
	fi
	kubectl apply -f deployments/k8s-local/manifests/00-namespace.yaml

create-local-secrets: validate-secrets create-local-namespace
	kubectl create secret generic bgc-data-portal-secret \
	  --from-env-file=$(ENV_FILE) -n bgc-local \
	  --dry-run=client -o yaml | kubectl apply -f -

# ── Local dev loop ────────────────────────────────────────────────────────────
# Reclaimable threshold (GB) above which dev-preflight nags about running tidy.
# Tune by editing this number — when reclaimable Docker space crosses it, we
# warn and pause briefly before continuing so a Ctrl-C escape is possible.
DISK_RECLAIMABLE_WARN_GB := 10

# Sums GB-scale reclaimable across Images / Containers / Volumes / Build Cache.
# Sub-GB rows are ignored (they're not what fills a 100 GB Colima VM).
dev-preflight:
	@reclaim=$$(docker system df --format '{{.Reclaimable}}' 2>/dev/null \
	  | grep -oE '[0-9]+(\.[0-9]+)?GB' | sed 's/GB//' \
	  | awk '{s+=$$1} END {printf "%.0f", s+0}'); \
	if [ "$${reclaim:-0}" -ge "$(DISK_RECLAIMABLE_WARN_GB)" ]; then \
	  echo ""; \
	  echo "WARN: Docker has ~$${reclaim}GB reclaimable (threshold $(DISK_RECLAIMABLE_WARN_GB)GB)."; \
	  echo "      Run 'make tidy' to reclaim it before disk pressure breaks pods."; \
	  echo "      Continuing in 5s — Ctrl-C to abort."; \
	  sleep 5; \
	fi

dev: dev-preflight create-local-secrets
	skaffold dev -p local --cleanup=false

dev-full: dev-preflight create-local-secrets
	skaffold dev -p local-full --cleanup=false

dev-clean:
	skaffold delete -p local

deploy-local: create-local-secrets
	skaffold run -p local

delete-local:
	skaffold delete -p local

# ── Remote deploy (requires KUBE_CONTEXT env var) ─────────────────────────────
deploy-dev:
	skaffold run -p dev --kube-context $(KUBE_CONTEXT)

deploy-prod:
	skaffold run -p prod --kube-context $(KUBE_CONTEXT)

# ── Tests ─────────────────────────────────────────────────────────────────────
# pytest config (DJANGO_SETTINGS_MODULE, pythonpath) lives in the repo-root
# pyproject.toml, which isn't copied into the image (/app == django/). Set the
# settings module inline so in-pod pytest finds Django.
#
# Heavy clustering libs (igraph/leidenalg/umap) and pyhmmer live only in the
# worker image, so the clustering + protein-search tests importorskip in the
# django pod. Run TEST_POD=bgc-data-portal-celery to exercise those too.
TEST_POD ?= bgc-data-portal-django

test-unit:
	kubectl exec -n bgc-local deploy/$(TEST_POD) -- \
	  env DJANGO_SETTINGS_MODULE=bgc_data_portal.settings pytest tests/unit/ -q

test-integration:
	kubectl exec -n bgc-local deploy/$(TEST_POD) -- \
	  env DJANGO_SETTINGS_MODULE=bgc_data_portal.settings pytest tests/integration/ -q

# E2E runs from the host (needs `pip install pytest-playwright && playwright
# install chromium`) against the Skaffold port-forward (django:80 -> :8080).
# The SPA mounts at /dashboard/. Override with E2E_URL=... for a remote deploy.
E2E_URL ?= http://localhost:8080/dashboard
test-e2e:
	pytest django/tests/e2e/playwright --e2e-v2-base-url $(E2E_URL) -q

# ── Observability ─────────────────────────────────────────────────────────────
logs-django:
	kubectl logs -f -n bgc-local deploy/bgc-data-portal-django

logs-celery:
	kubectl logs -f -n bgc-local deploy/bgc-data-portal-celery

shell:
	kubectl exec -it -n bgc-local deploy/bgc-data-portal-django -- bash

db-shell:
	kubectl exec -it -n bgc-local statefulset/postgres -- psql -U bgc_dp_pg_user mgnify_bgcs

# ── Cache management ───────────────────────────────────────────────────────────
clear-cache-redis:
	@echo "Flushing Redis..."
	kubectl exec -n bgc-local deploy/redis -- redis-cli FLUSHALL

clear-cache-celery:
	@echo "Purging Celery task queues..."
	kubectl exec -n bgc-local deploy/bgc-data-portal-celery -- celery -A bgc_data_portal purge -f

clear-cache-django:
	@echo "Clearing Django cache..."
	kubectl exec -n bgc-local deploy/bgc-data-portal-django -- python manage.py shell -c "from django.core.cache import cache; cache.clear()"

clear-cache: clear-cache-redis clear-cache-celery clear-cache-django

# ── Protein search index ──────────────────────────────────────────────────────
# Runs inside the Celery pod — that's where the mount lives. Use --rebuild on
# first bootstrap or after a TRUNCATE; the default is incremental append.
build-protein-index:
	kubectl exec -n bgc-local deploy/bgc-data-portal-celery -- \
	  python manage.py build_protein_search_index --rebuild

update-protein-index:
	kubectl exec -n bgc-local deploy/bgc-data-portal-celery -- \
	  python manage.py build_protein_search_index --append

# ── Real-data seeding ─────────────────────────────────────────────────────────
# Delegates to scripts/seed-real-data.sh — copies each *.tgz to the django pod
# as a single file (robust for large archives), extracts inside the pod, and
# runs load_discovery_data. First archive --truncate, rest additive.
# Per-archive stderr captured to a temp log dir; pod re-resolved per iteration.
seed-real-data:
	STAGED_FILES_DIR=$(STAGED_FILES_DIR) ./scripts/seed-real-data.sh

# ── Workspace (Claude Code in isolated pod) ──────────────────────────────────
workspace-enter:
	./scripts/workspace.sh enter

workspace-login:
	./scripts/workspace.sh login

workspace-claude:
	./scripts/workspace.sh claude

workspace-sync-in:
	./scripts/workspace.sh sync-in

workspace-sync-out:
	./scripts/workspace.sh sync-out

workspace-patch:
	./scripts/workspace.sh patch

workspace-apply-patch:
	./scripts/workspace.sh apply-patch

workspace-set-api-key:
	./scripts/workspace.sh set-api-key

workspace-restart:
	./scripts/workspace.sh restart

# ── Disk reclaim ──────────────────────────────────────────────────────────────
# Routine cleanup: prune dangling images on host Docker AND inside the Kind node.
# Run between heavy rebuild sessions when 'docker system df' shows growing
# RECLAIMABLE space. Safe — does not touch running containers or named volumes.
clean-images:
	@echo "Pruning dangling images in Docker daemon..."
	docker image prune -af
	@echo "Pruning unused images in Kind containerd (--timeout=300s)..."
	docker exec bgc-local-control-plane crictl --timeout=300s rmi --prune || \
	  echo "WARN: crictl prune incomplete (node likely overloaded). Re-run 'make tidy', or 'make nuke' for a hard reset."
	@echo "Done. Run 'docker system df' to verify."

# Routine sweep: clean-images PLUS the Docker build cache. Build cache grows
# silently with each rebuild (saw it hit 25GB in normal use) and isn't touched
# by clean-images. Run 'make tidy' weekly or when dev-preflight nags.
tidy: clean-images
	@echo "Pruning Docker build cache..."
	docker builder prune -af
	@echo ""
	@echo "Disk after tidy:"
	@docker system df

# Nuclear reset: delete the Kind cluster AND prune everything Docker, including
# named volumes. WIPES local Postgres data (db_data volume). Use when 'make
# tidy' isn't enough or you want a known-good clean slate.
nuke: cluster-delete
	@echo "Pruning Docker daemon (images, containers, build cache, networks, VOLUMES)..."
	docker system prune -af --volumes
	@echo "Cluster deleted and Docker pruned. Next 'make dev' starts cold."
