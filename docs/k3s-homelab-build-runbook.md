# 🧱 K3s Homelab Build Runbook (v1)

## Overview
This document describes the setup of a local Kubernetes (k3s) cluster using Multipass, MetalLB, and Traefik ingress, along with deployment of a backend service.

---

## 1. Environment

- Host: macOS (Apple Silicon)
- VM platform: Multipass
- Kubernetes: k3s
- Networking:
  - MetalLB (LoadBalancer)
  - Traefik (Ingress)

---

## 2. Node Configuration

| Node         | CPU | Memory | Disk |
|--------------|-----|--------|------|
| controlplane | 2   | 4GB    | 60GB |
| node01       | 2   | 4GB    | 40GB |
| node02       | 2   | 4GB    | 40GB |

---

## 3. Create VMs

```bash
multipass launch 22.04 --name controlplane --cpus 2 --memory 4G --disk 60G
multipass launch 22.04 --name node01 --cpus 2 --memory 4G --disk 40G
multipass launch 22.04 --name node02 --cpus 2 --memory 4G --disk 40G
```

---

## 4. Install k3s (Control Plane)

```bash
multipass shell controlplane
curl -sfL https://get.k3s.io | sh -
sudo cat /var/lib/rancher/k3s/server/node-token
```

---

## 5. Join Worker Nodes

```bash
multipass shell node01
curl -sfL https://get.k3s.io | \
K3S_URL=https://<CONTROLPLANE_IP>:6443 \
K3S_TOKEN='<TOKEN>' \
sh -
```

Repeat for node02.

---

## 6. Verify Cluster

```bash
sudo k3s kubectl get nodes -o wide
```

---

## 7. Disable ServiceLB

```bash
sudo tee /etc/rancher/k3s/config.yaml <<EOF
disable:
  - servicelb
EOF

sudo systemctl restart k3s
```

---

## 8. Install MetalLB

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/main/config/manifests/metallb-native.yaml
```

---

## 9. Configure IP Pool

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

---

## 10. Validate LoadBalancer

```bash
kubectl create deployment nginx --image=nginx
kubectl expose deployment nginx --port=80 --type=LoadBalancer
kubectl get svc nginx
```

---

## 11. Configure Ingress

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

---

## 12. Local DNS (Mac)

```bash
echo "192.168.2.240 nginx.lab secure-ai.lab" | sudo tee -a /etc/hosts
```

---

## 13. Backend Deployment

### Image Build

```bash
docker build -t secure-ai-backend:step1 -f Dockerfile.backend .
docker save secure-ai-backend:step1 -o secure-ai-backend-step1.tar
```

### Import into k3s

```bash
sudo k3s ctr -n k8s.io images import secure-ai-backend-step1.tar
```

### Deployment Notes

- Use full image name:
  ```
  docker.io/library/secure-ai-backend:step1
  ```
- Set:
  ```
  imagePullPolicy: Never
  ```
- Pin to controlplane:
  ```
  nodeSelector:
    kubernetes.io/hostname: controlplane
  ```

---

## 14. Validation

```bash
curl http://secure-ai.lab/docs
```

---

## 15. Lessons Learned

- Disk size matters (20GB is insufficient for ML images)
- k3s uses containerd namespace `k8s.io`
- `ctr` ≠ `crictl` visibility
- Always match exact image name
- Use `/etc/hosts` for local DNS
- Prefer clean rebuild over debugging corrupted state
