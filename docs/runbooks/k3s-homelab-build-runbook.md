# K3s Homelab Build Runbook (v3)

## Goal

Build a reproducible local platform on macOS using Multipass and k3s, with:

- 3-node Kubernetes cluster
- MetalLB load balancer
- Traefik ingress
- Longhorn persistent storage
- Backend deployment with persistent app data
- GitHub Actions CD using a self-hosted runner
- Prometheus + Grafana monitoring
- TLS via cert-manager

---

## Final Platform Summary

### Nodes

| Node | Role | CPU | Memory | Disk |
|---|---|---:|---:|---:|
| controlplane | k3s server | 2 | 4G | 60G |
| node01 | worker | 2 | 4G | 40G |
| node02 | worker | 2 | 4G | 40G |

### Key Endpoints

| Service | URL | Notes |
|---|---|---|
| Backend docs | `https://secure-ai.lab/docs` | Served through Traefik with TLS |
| Grafana | `https://grafana.lab` | Redirects to `/login` |
| Traefik LB IP | `192.168.2.240` | Assigned by MetalLB |
| Nginx test app | `http://nginx.lab` | Ingress validation |

---

## Architecture

```text
Mac (Host)
│
├── Multipass
│   ├── controlplane (k3s server)
│   ├── node01 (worker)
│   └── node02 (worker)
│
├── k3s
│   ├── Traefik ingress
│   ├── Longhorn storage
│   ├── MetalLB
│   ├── Prometheus + Grafana
│   └── secure-ai-backend
│
├── Local DNS via /etc/hosts
│   ├── secure-ai.lab
│   ├── grafana.lab
│   └── nginx.lab
│
└── GitHub Actions
    └── Self-hosted runner on Mac deploys to local cluster
```

---

## 1. Provision VMs

```bash
multipass delete controlplane node01 node02
multipass purge

multipass launch 22.04 --name controlplane --cpus 2 --memory 4G --disk 60G
multipass launch 22.04 --name node01 --cpus 2 --memory 4G --disk 40G
multipass launch 22.04 --name node02 --cpus 2 --memory 4G --disk 40G

multipass list
```

Example final node IPs:

- `controlplane`: `192.168.2.12`
- `node01`: `192.168.2.13`
- `node02`: `192.168.2.14`

---

## 2. Install k3s

### Control plane

```bash
multipass shell controlplane
curl -sfL https://get.k3s.io | sh -
sudo k3s kubectl get nodes -o wide
sudo cat /var/lib/rancher/k3s/server/node-token
```

### Join workers

On `node01`:

```bash
curl -sfL https://get.k3s.io | \
K3S_URL=https://192.168.2.12:6443 \
K3S_TOKEN='<TOKEN>' \
sh -
```

On `node02`:

```bash
curl -sfL https://get.k3s.io | \
K3S_URL=https://192.168.2.12:6443 \
K3S_TOKEN='<TOKEN>' \
sh -
```

### Validate

```bash
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A -o wide
```

---

## 3. Install MetalLB and Ingress Baseline

### Disable built-in ServiceLB

On `controlplane`:

```bash
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml >/dev/null <<'EOF'
disable:
  - servicelb
EOF

sudo systemctl restart k3s
```

### Install MetalLB

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/main/config/manifests/metallb-native.yaml
kubectl get pods -n metallb-system
```

### Configure address pool

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: homelab-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.2.240-192.168.2.250
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: homelab-l2
  namespace: metallb-system
spec: {}
```

Apply:

```bash
kubectl apply -f metallb-config.yaml
```

### Validate using nginx

```bash
kubectl create deployment nginx --image=nginx
kubectl expose deployment nginx --port=80 --type=LoadBalancer
kubectl get svc nginx
kubectl get svc -n kube-system traefik
```

Expected:
- `nginx` gets a MetalLB external IP such as `192.168.2.241`
- `traefik` gets `192.168.2.240`

### Create ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
spec:
  ingressClassName: traefik
  rules:
  - host: nginx.lab
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx
            port:
              number: 80
```

Apply and validate:

```bash
kubectl apply -f nginx-ingress.yaml
kubectl get ingress
```

### Local DNS

On Mac `/etc/hosts`:

```text
192.168.2.240 nginx.lab secure-ai.lab grafana.lab
```

---

## 4. Backend Deployment

### Important design choices

- Build backend image locally on Mac
- Import image into k3s containerd
- Use Longhorn-backed PVC for `/app/data`
- Run backend through Traefik ingress
- Keep secrets out of git

### Backend image notes

Use a backend-specific Dockerfile such as `Dockerfile.backend`.

Important fix:
- Do **not** copy a local `data/` directory into the image
- Instead create the path during build and mount Longhorn storage there at runtime

Recommended pattern in `Dockerfile.backend`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.k8s-step1.txt /app/backend/requirements.k8s-step1.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.k8s-step1.txt

COPY backend /app/backend
COPY docs /app/docs
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build locally

```bash
docker build -t secure-ai-backend:step1 -f Dockerfile.backend .
docker save secure-ai-backend:step1 -o secure-ai-backend-step1.tar
```

### Transfer and import into k3s

```bash
multipass transfer secure-ai-backend-step1.tar controlplane:/home/ubuntu/secure-ai-backend-step1.tar

multipass exec controlplane -- sudo k3s ctr -n k8s.io images import /home/ubuntu/secure-ai-backend-step1.tar
multipass exec controlplane -- sudo k3s ctr -n k8s.io images ls | grep secure-ai-backend
```

Important:
- Use the `k8s.io` containerd namespace
- The exact image name used by the Deployment must match the imported image ref

### Secret manifest

Create a local-only manifest such as `deploy/k8s/backend/secret.yaml` and keep it out of git.

Example:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: secure-ai-backend-secret
type: Opaque
stringData:
  ADMIN_PASSWORD_HASH: "..."
  USER_PASSWORD_HASH: "..."
```

### PVC

`deploy/k8s/backend/pvc.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: secure-ai-backend-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 10Gi
```

### Deployment

Key points in `deploy/k8s/backend/deployment.yaml`:

- pin to `controlplane` if image exists only there
- use `imagePullPolicy: Never`
- use the exact imported image ref
- set `DATA_DIR=/app/data`
- mount the PVC at `/app/data`

Representative spec excerpt:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secure-ai-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: secure-ai-backend
  template:
    metadata:
      labels:
        app: secure-ai-backend
    spec:
      nodeSelector:
        kubernetes.io/hostname: controlplane
      containers:
        - name: backend
          image: docker.io/library/secure-ai-backend:step1
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
          env:
            - name: PYTHONUNBUFFERED
              value: "1"
            - name: DATA_DIR
              value: /app/data
            - name: ADMIN_PASSWORD_HASH
              valueFrom:
                secretKeyRef:
                  name: secure-ai-backend-secret
                  key: ADMIN_PASSWORD_HASH
            - name: USER_PASSWORD_HASH
              valueFrom:
                secretKeyRef:
                  name: secure-ai-backend-secret
                  key: USER_PASSWORD_HASH
          volumeMounts:
            - name: backend-storage
              mountPath: /app/data
          readinessProbe:
            httpGet:
              path: /docs
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /docs
              port: 8000
            initialDelaySeconds: 20
            periodSeconds: 20
      volumes:
        - name: backend-storage
          persistentVolumeClaim:
            claimName: secure-ai-backend-pvc
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: secure-ai-backend
spec:
  selector:
    app: secure-ai-backend
  ports:
    - port: 80
      targetPort: 8000
```

### Ingress

TLS is added later, but plain routing starts like this:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secure-ai-backend
spec:
  ingressClassName: traefik
  rules:
    - host: secure-ai.lab
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: secure-ai-backend
                port:
                  number: 80
```

### Apply

```bash
kubectl apply -f deploy/k8s/backend/secret.yaml
kubectl apply -f deploy/k8s/backend/pvc.yaml
kubectl apply -f deploy/k8s/backend/deployment.yaml
kubectl apply -f deploy/k8s/backend/service.yaml
kubectl apply -f deploy/k8s/backend/ingress.yaml

kubectl get pods -o wide
kubectl logs -l app=secure-ai-backend
```

### Validate

```bash
curl -I http://secure-ai.lab/docs
```

---

## 5. Persistent Storage with Longhorn

### Install Longhorn

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.6.2/deploy/longhorn.yaml
kubectl get pods -n longhorn-system -w
```

### Expose Longhorn UI

Change the `longhorn-frontend` service from `ClusterIP` to `LoadBalancer`:

```bash
kubectl -n longhorn-system edit svc longhorn-frontend
```

Then check:

```bash
kubectl get svc -n longhorn-system
```

### Validate Longhorn storage class

```bash
kubectl get storageclass
```

### Validate persistence

Create a test PVC and pod, write a file, delete the pod, recreate it, and verify the file persists.

This validates real stateful storage before using it for the backend.

---

## 6. Access the Cluster from the Mac

Copy the k3s kubeconfig from `controlplane` and replace `127.0.0.1` with the actual controlplane IP.

One-liner:

```bash
multipass exec controlplane -- sudo cat /etc/rancher/k3s/k3s.yaml | sed 's/127.0.0.1/192.168.2.12/' > ~/.kube/config

chmod 600 ~/.kube/config
kubectl get nodes -o wide
```

---

## 7. GitHub Actions CD

### Why self-hosted runner

A GitHub-hosted runner cannot reach a local Multipass cluster on the Mac, so deployment must run from a self-hosted runner on the same Mac.

### Runner setup

Configure a self-hosted GitHub Actions runner for the repo on the Mac.

### Deploy script

Example `script/deploy_backend.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="secure-ai-backend"
IMAGE_TAG="${1:-step1}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
TAR_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
CONTROLPLANE_VM="controlplane"

echo "==> Building Docker image: ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" -f Dockerfile.backend .

echo "==> Saving image tar: ${TAR_FILE}"
rm -f "${TAR_FILE}"
docker save "${FULL_IMAGE}" -o "${TAR_FILE}"

echo "==> Transferring image tar to Multipass controlplane"
multipass transfer "${TAR_FILE}" "${CONTROLPLANE_VM}:/home/ubuntu/${TAR_FILE}"

echo "==> Importing image into k3s containerd"
multipass exec "${CONTROLPLANE_VM}" -- sudo k3s ctr -n k8s.io images import "/home/ubuntu/${TAR_FILE}"

echo "==> Verifying image exists in containerd"
multipass exec "${CONTROLPLANE_VM}" -- sudo k3s ctr -n k8s.io images ls | grep "${IMAGE_NAME}"

echo "==> Applying Kubernetes manifests"
kubectl apply -f deploy/k8s/backend/pvc.yaml
kubectl apply -f deploy/k8s/backend/deployment.yaml
kubectl apply -f deploy/k8s/backend/service.yaml
kubectl apply -f deploy/k8s/backend/ingress.yaml

echo "==> Restarting deployment"
kubectl rollout restart deployment secure-ai-backend
kubectl rollout status deployment secure-ai-backend --timeout=300s

echo "==> Cleaning transferred tar from controlplane"
multipass exec "${CONTROLPLANE_VM}" -- rm -f "/home/ubuntu/${TAR_FILE}"

echo "==> Deployment complete"
kubectl get pods -o wide
```

### Workflow

`.github/workflows/deploy-backend.yml`

```yaml
name: Deploy Backend to Local k3s

on:
  push:
    branches:
      - main
    paths:
      - 'backend/**'
      - 'deploy/k8s/backend/**'
      - 'Dockerfile.backend'
      - '.github/workflows/deploy-backend.yml'
      - 'script/deploy_backend.sh'

jobs:
  deploy:
    runs-on: self-hosted

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Debug environment
        run: |
          echo "PATH=$PATH"
          whoami
          pwd
          which kubectl || true
          which multipass || true
          docker --version || true
          kubectl version --client || true
          multipass version || true

      - name: Verify kubectl context
        run: |
          kubectl config current-context || true
          kubectl get nodes -o wide

      - name: Ensure deploy script is executable
        run: chmod +x ./script/deploy_backend.sh

      - name: Deploy backend
        run: ./script/deploy_backend.sh step1
```

### Validation

A successful workflow run should build, transfer, import, apply, and restart the backend Deployment.

---

## 8. Monitoring with Prometheus and Grafana

### Install Helm on Mac

```bash
brew install helm
helm version
```

### Add Prometheus community repo

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

### Values file

`deploy/k8s/monitoring/kube-prometheus-stack-values.yaml`

```yaml
grafana:
  adminPassword: admin123
  persistence:
    enabled: true
    storageClassName: longhorn
    accessModes:
      - ReadWriteOnce
    size: 5Gi
  service:
    type: ClusterIP
  ingress:
    enabled: true
    ingressClassName: traefik
    hosts:
      - grafana.lab
    path: /
    pathType: Prefix

prometheus:
  prometheusSpec:
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: longhorn
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 10Gi

alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: longhorn
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 2Gi
```

### Install stack

```bash
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f deploy/k8s/monitoring/kube-prometheus-stack-values.yaml
```

### Validate

```bash
kubectl get pods -n monitoring
kubectl get pvc -n monitoring
kubectl get ingress -n monitoring
```

Example healthy results:
- Grafana ingress at `grafana.lab`
- PVCs for Grafana, Prometheus, Alertmanager all `Bound`

### Access

```bash
curl -I http://grafana.lab
open http://grafana.lab
```

Default credentials from this setup:
- user: `admin`
- password: `admin123`

---

## 9. TLS with cert-manager

### Install cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true
```

### Validate

```bash
kubectl get pods -n cert-manager
```

### Create self-signed ClusterIssuer

`deploy/k8s/cert-manager/selfsigned-clusterissuer.yaml`

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-clusterissuer
spec:
  selfSigned: {}
```

Apply:

```bash
kubectl apply -f deploy/k8s/cert-manager/selfsigned-clusterissuer.yaml
kubectl get clusterissuer
```

### Add TLS to backend ingress

`deploy/k8s/backend/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secure-ai-backend
  annotations:
    cert-manager.io/cluster-issuer: selfsigned-clusterissuer
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - secure-ai.lab
      secretName: secure-ai-lab-tls
  rules:
    - host: secure-ai.lab
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: secure-ai-backend
                port:
                  number: 80
```

### Add TLS to Grafana ingress

`deploy/k8s/monitoring/grafana-ingress-tls.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: monitoring-grafana
  namespace: monitoring
  annotations:
    cert-manager.io/cluster-issuer: selfsigned-clusterissuer
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - grafana.lab
      secretName: grafana-lab-tls
  rules:
    - host: grafana.lab
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: monitoring-grafana
                port:
                  number: 80
```

Apply:

```bash
kubectl apply -f deploy/k8s/backend/ingress.yaml
kubectl apply -f deploy/k8s/monitoring/grafana-ingress-tls.yaml
```

### Validate certificates

```bash
kubectl get certificate -A
kubectl get secret secure-ai-lab-tls
kubectl get secret -n monitoring grafana-lab-tls
```

### Test HTTPS

```bash
curl -kI https://secure-ai.lab/docs
curl -kI https://grafana.lab
```

Expected:
- `secure-ai.lab/docs` returns `200`
- `grafana.lab` returns `302` to `/login`

Browser warning is expected because the certs are self-signed.

---

## 10. Git Workflow

Recommended at the end of each step:

```bash
git status
git add <relevant files>
git commit -m "<step description>"
git push origin main
```

Push after every validated step to avoid losing progress.

---

## 11. Troubleshooting Notes

### `kubectl` hanging on Mac

Cause:
- stale or incorrect kubeconfig

Fix:
- copy `/etc/rancher/k3s/k3s.yaml` from controlplane
- replace `127.0.0.1` with actual controlplane IP
- save to `~/.kube/config`

### `ErrImageNeverPull`

Typical causes:
- image imported into wrong containerd namespace
- deployment image ref does not exactly match imported image
- pod scheduled on a node that does not have the image

Fixes:
- import with `sudo k3s ctr -n k8s.io images import ...`
- use exact image name in Deployment
- pin Deployment to `controlplane` if image only exists there

### `COPY data /app/data` build failure in GitHub Actions

Cause:
- `data/` is not committed to GitHub

Fix:
- do not copy runtime data into the image
- create `/app/data` during image build
- mount PVC there at runtime

### `pvc.yaml` missing in workflow

Cause:
- workflow referenced a manifest not yet committed

Fix:
- commit the PVC manifest to the repo

### Read-only filesystem / no space left on device

Cause:
- VM disk too small for ML images and containerd snapshots

Fix:
- rebuild nodes with larger disks
- `controlplane` 60G
- workers 40G

### kubeadm cluster drift and cert expiry

Cause:
- old control plane IPs and expired certificates

Fix:
- switch to k3s for local lab simplicity

### Multipass instance in unknown state / stuck QEMU

Fix:
- stop forcefully
- kill stuck qemu processes if needed
- purge and rebuild the VM cleanly

---

## 12. Lessons Learned

- k3s is a better fit than kubeadm for this local lab
- disk sizing matters a lot for ML-oriented containers
- Longhorn should be added before trying to persist app state
- GitHub-hosted runners cannot directly deploy into a local Multipass cluster
- exact image naming matters when using `imagePullPolicy: Never`
- pushing after every validated step prevents rework and confusion

---

## 13. Current Status

Completed:

- k3s cluster rebuild
- MetalLB
- Traefik ingress
- Longhorn
- backend deployment
- backend persistent storage
- self-hosted GitHub Actions deploy pipeline
- Prometheus + Grafana
- TLS with cert-manager

---

## 14. Suggested Next Steps

- replace self-signed certs with a more formal internal CA flow
- add architecture diagrams
- add application-specific dashboards in Grafana
- split backend into lighter deployable units if image size remains high
- add CI checks before CD deploy
- add rollback/versioned image tags