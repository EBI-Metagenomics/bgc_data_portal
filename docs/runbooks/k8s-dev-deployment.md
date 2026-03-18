# k8s-dev Deployment

Deploy the BGC Data Portal to the EBI HL Kubernetes cluster (experimental namespace).

## Prerequisites

- Access to `quay.io/microbiome-informatics` — log in with `docker login quay.io`
- `kubeconfig` for the EBI HL cluster (ask the team for access)
- `skaffold` >= 2.13 and `kubectl` >= 1.29

## Deploying

```bash
# Build Dockerfile.dev image, push to quay.io, and apply k8s-dev manifests
KUBE_CONTEXT=<your-ebi-kube-context> make deploy-dev
```

This runs `skaffold run -p dev` which:
1. Builds `quay.io/microbiome-informatics/bgc_dp_web_site` from `django/Dockerfile.dev`
2. Pushes the image to quay.io (tagged with the git commit SHA)
3. Applies `deployments/k8s-dev/ebi-wp-k8s-hl.yaml` to namespace `bgc-data-portal-hl-exp`

## CI-Triggered Builds

Every push to `main` that modifies `django/` triggers the
`.github/workflows/release.yml` pipeline, which:
- Builds and pushes the image automatically
- Tags it with the short git SHA

No manual push is needed for routine development — CI handles it.

## Viewing Logs

```bash
kubectl logs -f -n bgc-data-portal-hl-exp deploy/bgc-data-portal-django \
  --context <your-ebi-kube-context>
```

## Post-Deploy Verification

```bash
# Check the API docs endpoint responds
curl -I https://bgc-portal-dev.mgnify.org/api/docs

# Run unit tests inside the running pod
kubectl exec -n bgc-data-portal-hl-exp deploy/bgc-data-portal-django \
  --context <your-ebi-kube-context> -- pytest tests/unit/ -q
```

## Ingress

The dev environment is accessible at: `https://bgc-portal-dev.mgnify.org`

(Hostname and TLS are configured in `deployments/k8s-dev/ebi-wp-k8s-hl.yaml`.)
