# k8s-microservice-gitops

![ci](https://github.com/seunnuga93/k8s-microservice-gitops/actions/workflows/ci.yml/badge.svg)

A small Python API taken all the way from code to Kubernetes with a GitOps workflow:
tested and scanned in GitHub Actions, packaged as a hardened container, described by a
Helm chart, and deployed by ArgoCD pulling from this repo.

## Flow

```
 PR ──► ci.yml: ruff + pytest ─► helm lint + kubeconform ─► docker build ─► trivy scan ─► smoke test
                                                                                     │
 merge to main ──────────────────────────────────────────────────► push ghcr.io/…:<sha>
                                                                                     │
                       deploy-dev job commits  tag: "<sha>"  to values-dev.yaml ◄────┘
                                                     │
                     ArgoCD (watching this repo) ◄───┘  auto-sync ─► namespace inventory-dev
                     Prod: bump values-prod.yaml in a PR, review, merge, manual sync
```

CI never holds cluster credentials. The cluster pulls its desired state from git.

## Repo layout

| Path | What |
| --- | --- |
| `app/` | FastAPI service: `/items` CRUD, `/healthz`, `/readyz`, Prometheus `/metrics` |
| `charts/inventory-api/` | Helm chart: Deployment, Service, HPA, PDB, Ingress, NetworkPolicy, ServiceMonitor |
| `argocd/` | ArgoCD `Application` per environment |
| `.github/workflows/ci.yml` | Test, build, scan, push, and GitOps tag bump |

## Hardening in the chart

- Runs as UID 10001, `runAsNonRoot`, read-only root filesystem, all capabilities dropped, `RuntimeDefault` seccomp
- No service account token mounted
- Default-deny NetworkPolicy that only opens the app port
- `maxUnavailable: 0` rolling updates, PodDisruptionBudget, and spread across nodes
- Separate readiness and liveness probes

## Run locally

```bash
cd app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
PYTHONPATH=src uvicorn inventory.main:app --reload

curl -X POST localhost:8000/items -H 'content-type: application/json' -d '{"name":"widget","quantity":3}'
```

With Docker:

```bash
docker build -t inventory-api app
docker run -p 8000:8000 inventory-api
```

## Deploy to a cluster

Any cluster works, including a local [kind](https://kind.sigs.k8s.io/) one:

```bash
kind create cluster
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/inventory-api-dev.yaml

kubectl -n inventory-dev port-forward svc/inventory-api-dev 8080:80
curl localhost:8080/readyz
```

Or install the chart directly without ArgoCD:

```bash
helm install inventory-api charts/inventory-api -f charts/inventory-api/values-dev.yaml -n inventory-dev --create-namespace
```

> If the repo or GHCR package is private, ArgoCD needs repo credentials and the cluster needs an image pull secret.
