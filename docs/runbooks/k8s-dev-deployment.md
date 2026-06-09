# k8s-dev Deployment — SUPERSEDED

This runbook described the old `skaffold run -p dev` flow that applied the
hand-written `deployments/k8s-dev/ebi-wp-k8s-hl.yaml`. That path has been
**removed**: cloud deploys now render the canonical Helm chart
(`deployments/chart/`) from the private **`mgnify-bgcs-deployer`** repo.

To deploy cloud-dev:

```bash
# in a checkout of mgnify-bgcs-deployer (app repo as a sibling)
make render-dev                              # inspect what will be applied
cp envs/cloud-dev/secrets.template.env envs/cloud-dev/secrets.dev.env  # fill it
make secret-dev
make deploy-dev KUBE_CONTEXT=<your-ebi-kube-context>
```

Full deployment model, the dev (k3d) loop, and OCI chart publishing are in the
monorepo runbook:
`../../../../docs/runbooks/services/bgc_data_portal/deployment-helm.md`.
