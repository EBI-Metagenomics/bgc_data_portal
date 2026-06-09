# Local Dev Setup — SUPERSEDED

The local dev loop moved from **kind + rawYaml manifests** to **k3d + the canonical
Helm chart** (`deployments/chart/` rendered via Skaffold's Helm deployer). This
runbook's kind/`deployments/k8s-local/manifests/` instructions no longer apply.

## TL;DR

```bash
brew install helm@3 k3d kubectl skaffold make   # Skaffold needs Helm v3, NOT v4
make cluster-create                              # k3d cluster create bgc-local
cp deployments/.env.local.example deployments/.env.local   # defaults work as-is
make dev                                          # build → helm release on k3d → :8080
make dev-full                                     # …plus the workspace pod
```

App: <http://localhost:8080/dashboard/>. Hot-reload, `make reset-db`,
`make seed-real-data`, `make e2e-seed`, tests, and the cache/logs/shell helpers
are unchanged — see the repo `CLAUDE.md`.

Full deployment model, the k3d dev loop, and troubleshooting (disk-pressure
taint, image GC, wrong-cluster) live in the monorepo runbook:
`../../../../docs/runbooks/services/bgc_data_portal/deployment-helm.md`.
