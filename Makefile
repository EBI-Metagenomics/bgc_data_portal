.PHONY: cluster-create cluster-delete create-local-namespace create-local-secrets \
        dev dev-full dev-clean dev-preflight deploy-local delete-local selfhost \
        test-unit test-integration test-e2e logs shell db-shell validate-secrets \
        clear-cache-django clear-cache \
        seed-real-data reset-db e2e-seed \
        build-protein-index update-protein-index \
        clean-images tidy nuke lock \
        workspace-enter workspace-login workspace-claude workspace-sync-in workspace-sync-out \
        workspace-patch workspace-apply-patch workspace-set-api-key workspace-restart

ENV_FILE := deployments/.env.local
STAGED_FILES_DIR := ../../.SCRATCH/STAGED_FILES_SAMPLES

# ── Secrets validation ─────────────────────────────────────────────────────────
REQUIRED_VARS := DJANGO_SECRET_KEY DATABASE_URL POSTGRES_USER POSTGRES_PASSWORD \
                 POSTGRES_DB

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
# Pin the local kube context everywhere. A same-named KIND cluster
# (kind-bgc-local) may linger from before the k3d migration; relying on the
# *current* context risks deploying into (or, for reset-db, DROPing) the wrong
# one. The deploy path below targets $(KCTX) explicitly.
KCTX := k3d-bgc-local

cluster-create:
	k3d cluster create bgc-local
	# k3d cannot merge into a multi-file KUBECONFIG, which leaves k3d-bgc-local a
	# credential-less stub (deploys then silently hit whatever context is current).
	# Merge the cluster's creds into the first KUBECONFIG entry (or ~/.kube/config),
	# switch to it, and pin the namespace onto the context.
	KUBECONFIG="$(firstword $(subst :, ,$(KUBECONFIG)) $(HOME)/.kube/config)" \
	  k3d kubeconfig merge bgc-local --kubeconfig-merge-default --kubeconfig-switch-context
	kubectl config set-context $(KCTX) --namespace=bgc-local

cluster-delete:
	k3d cluster delete bgc-local

# ── Secrets ───────────────────────────────────────────────────────────────────
# Wait for any in-progress namespace deletion before re-applying. Without this,
# a fast-retry of `make dev` after a previous teardown hits:
#   "namespace bgc-local … is forbidden … is being terminated"
create-local-namespace:
	@if kubectl --context $(KCTX) get ns bgc-local -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Terminating; then \
	  echo "Namespace bgc-local is Terminating; waiting up to 120s for cleanup..."; \
	  kubectl --context $(KCTX) wait --for=delete ns/bgc-local --timeout=120s || \
	    (echo "ERROR: bgc-local stuck Terminating. Inspect: kubectl get ns bgc-local -o yaml" && exit 1); \
	fi
	kubectl --context $(KCTX) create namespace bgc-local --dry-run=client -o yaml | kubectl --context $(KCTX) apply -f -

create-local-secrets: validate-secrets create-local-namespace
	kubectl --context $(KCTX) create secret generic bgc-data-portal-secret \
	  --from-env-file=$(ENV_FILE) -n bgc-local \
	  --dry-run=client -o yaml | kubectl --context $(KCTX) apply -f -

# ── Local dev loop ────────────────────────────────────────────────────────────
# Reclaimable threshold (GB) above which dev-preflight nags about running tidy.
# Tune by editing this number — when reclaimable Docker space crosses it, we
# warn and pause briefly before continuing so a Ctrl-C escape is possible.
DISK_RECLAIMABLE_WARN_GB := 10

# Sums GB-scale reclaimable across Images / Containers / Volumes / Build Cache.
# Sub-GB rows are ignored (they're not what fills a 100 GB Colima VM).
# Skaffold's Helm deployer shells out to `helm` but is NOT yet compatible with
# Helm v4's post-renderer change (skaffold#9871) — it needs Helm v3. Resolve a
# v3 binary for the dev loop without disturbing the global helm: prefer the
# keg-only `helm@3`, else rely on a `helm` that is already v3 on PATH.
HELM3_DIR := $(shell brew --prefix helm@3 2>/dev/null)/bin

dev-preflight:
	@command -v k3d  >/dev/null 2>&1 || { echo "ERROR: k3d not found — the dev loop runs on k3d. Install: brew install k3d"; exit 1; }
	@if [ -x "$$(brew --prefix helm@3 2>/dev/null)/bin/helm" ]; then :; \
	 elif command -v helm >/dev/null 2>&1 && helm version --short 2>/dev/null | grep -q '^v3'; then :; \
	 else echo "ERROR: Skaffold needs Helm v3 (host helm is v4 or missing — skaffold#9871). Install: brew install helm@3"; exit 1; fi
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
	PATH="$(HELM3_DIR):$$PATH" skaffold dev -p local --kube-context $(KCTX) --cleanup=false

dev-full: dev-preflight create-local-secrets
	PATH="$(HELM3_DIR):$$PATH" skaffold dev -p local-full --kube-context $(KCTX) --cleanup=false

dev-clean:
	PATH="$(HELM3_DIR):$$PATH" skaffold delete -p local --kube-context $(KCTX)

deploy-local: create-local-secrets
	PATH="$(HELM3_DIR):$$PATH" skaffold run -p local --kube-context $(KCTX)

delete-local:
	PATH="$(HELM3_DIR):$$PATH" skaffold delete -p local --kube-context $(KCTX)

# ── Self-host (build from source, no registry) ────────────────────────────────
# Builds the prod images from the public-base Dockerfiles, imports them into k3d,
# and installs the canonical chart — for self-hosters without access to the
# private image registry. Options: scripts/selfhost-build.sh -h
selfhost:
	./scripts/selfhost-build.sh

# ── Cloud deploy ──────────────────────────────────────────────────────────────
# Cloud dev/prod deploys moved to the private mgnify-bgcs-deployer repo (Helm):
#   cd ../mgnify-bgcs-deployer && make deploy-dev|deploy-prod KUBE_CONTEXT=<ctx>

# ── Tests ─────────────────────────────────────────────────────────────────────
# pytest config (DJANGO_SETTINGS_MODULE, pythonpath) lives in the repo-root
# pyproject.toml, which isn't copied into the image (/app == django/). Set the
# settings module inline so in-pod pytest finds Django.
#
# Heavy clustering libs (igraph/leidenalg/umap) and pyhmmer live only in the
# worker image, so the clustering + protein-search tests importorskip in the
# django pod. Run TEST_POD=bgc-data-portal-worker to exercise those too.
TEST_POD ?= bgc-data-portal-django

test-unit:
	kubectl exec -n bgc-local deploy/$(TEST_POD) -- \
	  env DJANGO_SETTINGS_MODULE=bgc_data_portal.settings pytest tests/unit/ -q

test-integration:
	kubectl exec -n bgc-local deploy/$(TEST_POD) -- \
	  env DJANGO_SETTINGS_MODULE=bgc_data_portal.settings pytest tests/integration/ -q

# E2E runs from the host (needs pytest-playwright + `playwright install
# chromium`) against the Skaffold port-forward (django:80 -> :8080). The SPA
# mounts at /dashboard/. PYTEST defaults to bare `pytest` (works when the
# project venv is activated); point it at the venv directly otherwise, e.g.
#   make test-e2e PYTEST=.venv/bin/pytest
# Override the target with E2E_URL=... for a remote deployment.
PYTEST  ?= pytest
E2E_URL ?= http://localhost:8080/dashboard
test-e2e:
	$(PYTEST) django/tests/e2e/playwright --e2e-v2-base-url $(E2E_URL) -q

# ── Local DB reset + e2e seeding ──────────────────────────────────────────────
# DESTRUCTIVE. The squashed `discovery.0001_initial` won't apply to a DB that
# already recorded an older `discovery.0001_initial`, so an upgraded-in-place
# dev DB ends up on the stale schema (no `discovery_ibgc`). Drop the public
# schema and let the django migrate init-container rebuild the v2 schema from
# scratch. The v2 schema needs only ltree + btree_gist (created by the
# migration); pgvector was dropped, so nothing else to recreate.
reset-db:
	@echo ">> DROP + recreate public schema in mgnify_bgcs (DEV — destroys ALL data)"
	kubectl exec -n bgc-local postgres-0 -- \
	  psql -U bgc_dp_pg_user -d mgnify_bgcs -v ON_ERROR_STOP=1 \
	  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo ">> Restart django so the migrate init-container rebuilds the schema"
	kubectl rollout restart -n bgc-local deploy/bgc-data-portal-django
	kubectl rollout status -n bgc-local deploy/bgc-data-portal-django --timeout=300s

# Post-load steps that materialise the iBGC table and a clustering run so the
# dashboard (and the e2e suite) have something to render. Run AFTER loading raw
# data with `make seed-real-data`. Executes in the worker pod, which has the
# clustering libs (igraph/leidenalg/umap); --sync runs in-process.
e2e-seed:
	kubectl exec -n bgc-local deploy/bgc-data-portal-worker -- \
	  env DJANGO_SETTINGS_MODULE=bgc_data_portal.settings \
	  python manage.py run_bgc_clustering --rebuild-ibgc --apply --sync

# ── Observability ─────────────────────────────────────────────────────────────
logs-django:
	kubectl logs -f -n bgc-local deploy/bgc-data-portal-django

logs-worker:
	kubectl logs -f -n bgc-local deploy/bgc-data-portal-worker

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
	@echo "Pruning unused images in k3d containerd (--timeout=300s)..."
	docker exec k3d-bgc-local-server-0 crictl --timeout=300s rmi --prune || \
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

# Nuclear reset: delete the k3d cluster AND prune everything Docker, including
# named volumes. WIPES local Postgres data (db_data volume). Use when 'make
# tidy' isn't enough or you want a known-good clean slate.
nuke: cluster-delete
	@echo "Pruning Docker daemon (images, containers, build cache, networks, VOLUMES)..."
	docker system prune -af --volumes
	@echo "Cluster deleted and Docker pruned. Next 'make dev' starts cold."

# ── Dependency lockfiles ────────────────────────────────────────────────────────
# Recompile the fully-pinned requirements-*.lock files from the human-edited
# requirements-*.txt sources. Runs uv inside the prod base image (python:3.12-slim)
# resolving for linux/amd64 so the locks match the deployed images regardless of
# the host arch — nothing is installed on the host. Edit a requirements-*.txt to
# add/bump a top-level dep, then run `make lock` and commit the updated .lock files.
PY_PLATFORM := x86_64-unknown-linux-gnu
PY_VERSION := 3.12
lock:
	@echo "Recompiling requirements-*.lock (uv, linux/amd64, py$(PY_VERSION))..."
	docker run --rm -v "$(CURDIR)/django:/w" -w /w python:$(PY_VERSION)-slim sh -c '\
	  apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1 && \
	  pip install -q uv && \
	  for f in web ml worker dev; do \
	    echo "  - requirements-$$f.lock" && \
	    uv pip compile requirements-$$f.txt -o requirements-$$f.lock \
	      --python-platform $(PY_PLATFORM) --python-version $(PY_VERSION) \
	      --emit-index-url --no-header --quiet; \
	  done'
	@echo "Done. Review the diff and commit the updated lockfiles."
