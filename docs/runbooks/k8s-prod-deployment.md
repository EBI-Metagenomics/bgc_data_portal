# k8s-prod Deployment — SUPERSEDED

The old `skaffold run -p prod` flow (applying the hand-written
`deployments/k8s-prod/ebi-wp-k8s-hl.yaml`) has been **removed**. Cloud-prod now
renders the canonical Helm chart (`deployments/chart/`) from the private
**`mgnify-bgcs-deployer`** repo.

## Deploy cloud-prod

```bash
# in a checkout of mgnify-bgcs-deployer (app repo as a sibling)
make render-prod                               # inspect what will be applied
make verify-prod                               # render matches the golden snapshot
make secret-prod                               # from envs/cloud-prod/secrets.prod.env
make deploy-prod KUBE_CONTEXT=<ebi-context>                    # local chart
make deploy-prod KUBE_CONTEXT=<ebi-context> CHART_VERSION=x.y.z  # pinned OCI chart
```

## Production image (unchanged)

Release Please monitors `main` and opens a release PR on `feat:`/`fix:` commits;
merging it bumps `version.txt` + `CHANGELOG.md` and creates a GitHub Release/tag.
The production image is built by `.github/workflows/release.yml` (from
`django/Dockerfile`, runs `collectstatic`) when a commit message contains
`"release portal"`, and pushed to
`quay.io/microbiome-informatics/bgc_dp_web_site:<tag>`. The Helm **chart** is
published separately to the OCI registry by `.github/workflows/publish-chart.yml`.

Full deployment model + the dev (k3d) loop:
`../../../../docs/runbooks/services/bgc_data_portal/deployment-helm.md`.
