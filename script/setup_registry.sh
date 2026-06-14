#!/usr/bin/env bash
set -euo pipefail

REGISTRY_IP="192.168.2.15"
REGISTRY_HOST="registry.lab:30500"
CONTROLPLANE_VM="controlplane"
WORKER_VMS=("node01" "node02")
NAMESPACE="secure-ai"

echo "==> Applying registry manifests"
kubectl apply -f deploy/k8s/registry/deployment.yaml
kubectl apply -f deploy/k8s/registry/service.yaml

echo "==> Waiting for registry to be ready"
kubectl rollout status deployment/registry -n "${NAMESPACE}" --timeout=120s

echo "==> Configuring k3s nodes to allow insecure registry pulls"
REGISTRIES_YAML="mirrors:
  \"${REGISTRY_HOST}\":
    endpoint:
      - \"http://${REGISTRY_IP}:30500\""

echo "  --> ${CONTROLPLANE_VM}"
printf '%s\n' "${REGISTRIES_YAML}" | multipass exec "${CONTROLPLANE_VM}" -- sudo tee /etc/rancher/k3s/registries.yaml > /dev/null
multipass exec "${CONTROLPLANE_VM}" -- sudo systemctl restart k3s

for VM in "${WORKER_VMS[@]}"; do
  echo "  --> ${VM}"
  printf '%s\n' "${REGISTRIES_YAML}" | multipass exec "${VM}" -- sudo tee /etc/rancher/k3s/registries.yaml > /dev/null
  multipass exec "${VM}" -- sudo systemctl restart k3s-agent
done

echo ""
echo "==> Registry is running at http://${REGISTRY_HOST}"
echo ""
echo "==> Mac setup required (one-time):"
echo "    1. Add to /etc/hosts:"
echo "       ${REGISTRY_IP} registry.lab"
echo "    2. Add to Docker Desktop → Settings → Docker Engine:"
echo "       \"insecure-registries\": [\"${REGISTRY_HOST}\"]"
echo "    3. Restart Docker Desktop"
