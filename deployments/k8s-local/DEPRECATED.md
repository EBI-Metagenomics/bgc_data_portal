# DEPRECATED — superseded by the Helm chart

The local dev loop now renders the canonical chart (`deployments/chart/`) via
Skaffold's Helm deployer on **k3d** (see `skaffold.yaml`, profiles `local` /
`local-full`, and `docs/runbooks/services/bgc_data_portal/deployment-helm.md`).

These files are no longer used by `make dev`:

- `manifests/` — replaced by `chart/` + `chart/values-laptop.yaml`
- `manifests-workspace/` — replaced by the chart's `workspace.yaml`
  (`workspace.enabled`, layered via `chart/values-workspace.yaml`)
- `kind-cluster.yaml` — removed; the substrate is k3d (`make cluster-create`)

They are kept for one verification cycle as a rollback path. **Delete this whole
directory once `make dev` on k3d is confirmed working.** `.env.local.example`
stays (it seeds the dev Secret); it will move alongside the chart on cleanup.
