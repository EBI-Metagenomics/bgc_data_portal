# bgc-data-portal Helm chart

Canonical, single-source deployment for the BGC Data Portal. One chart renders
three targets; pick one by passing its values file (the base `values.yaml` is a
minimal skeleton and is **not** a usable target on its own):

| Target | Values | Where |
|--------|--------|-------|
| laptop / self-host | `values-laptop.yaml` | here (public) |
| cloud-dev | `envs/cloud-dev/values.yaml` | `mgnify-bgcs-deployer` (private) |
| cloud-prod | `envs/cloud-prod/values.yaml` | `mgnify-bgcs-deployer` (private) |

```bash
# laptop / self-host (see docs/runbooks/.../self-host.md)
helm install bgc . -f values-laptop.yaml --namespace bgc-local

# cloud (run from the deployer repo)
make render-prod && make verify-prod && make deploy-prod KUBE_CONTEXT=<ctx>
```

Design notes and the migration plan live in
`docs/runbooks/services/bgc_data_portal/deployment-helm.md`.

**Conventions**
- Templates are thin skeletons; structurally-varying blocks (`env`, `command`,
  `volumes`, probes, `securityContext`, ingress rules) are passed through
  verbatim from values, so a target's values file fully describes its pods.
- Helm deep-merges maps but replaces lists — keep map-shaped, target-specific
  settings empty in `values.yaml` and declare them per target.
- `scripts/verify_parity.py` (deployer repo) proves a render matches a manifest.
