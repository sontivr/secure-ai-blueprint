#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="secure-ai-frontend"
IMAGE_TAG="${1:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
TAR_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
CONTROLPLANE_VM="controlplane"
WORKER_VMS=("node01" "node02")
NAMESPACE="secure-ai"

echo "==> Building Docker image: ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" -f frontend/Dockerfile frontend/

echo "==> Saving image tar: ${TAR_FILE}"
rm -f "${TAR_FILE}"
docker save "${FULL_IMAGE}" -o "${TAR_FILE}"

echo "==> Preflight: checking all Multipass VMs are running"
ALL_VMS=("${CONTROLPLANE_VM}" "${WORKER_VMS[@]}")
for VM in "${ALL_VMS[@]}"; do
  STATUS=$(multipass list --format csv 2>/dev/null | awk -F',' -v name="${VM}" '$1==name {print $2}')
  if [[ "${STATUS}" != "Running" ]]; then
    echo "  [ERROR] VM '${VM}' is not running (status: '${STATUS:-not found}'). Start it with: multipass start ${VM}"
    exit 1
  fi
  echo "  [OK] ${VM} is Running"
done

echo "==> Transferring and importing image to all nodes"
for VM in "${CONTROLPLANE_VM}" "${WORKER_VMS[@]}"; do
  echo "  --> ${VM}"
  multipass transfer "${TAR_FILE}" "${VM}:/home/ubuntu/${TAR_FILE}"
  multipass exec "${VM}" -- sudo k3s ctr -n k8s.io images import "/home/ubuntu/${TAR_FILE}"
  multipass exec "${VM}" -- rm -f "/home/ubuntu/${TAR_FILE}"
done

echo "==> Verifying image exists on controlplane"
multipass exec "${CONTROLPLANE_VM}" -- sudo k3s ctr -n k8s.io images ls | grep "${IMAGE_NAME}"

echo "==> Applying Kubernetes manifests"
kubectl apply -f deploy/k8s/frontend/service.yaml
kubectl apply -f deploy/k8s/frontend/ingress.yaml

echo "==> Deploying image: ${FULL_IMAGE}"
sed "s|secure-ai-frontend:IMAGE_TAG|secure-ai-frontend:${IMAGE_TAG}|g" \
  deploy/k8s/frontend/deployment.yaml | kubectl apply -f -

echo "==> Restarting deployment to pick up new image"
kubectl rollout restart deployment/secure-ai-frontend -n "${NAMESPACE}"

echo "==> Waiting for rollout"
kubectl rollout status deployment secure-ai-frontend -n "${NAMESPACE}" --timeout=180s

echo "==> Cleaning local tar"
rm -f "${TAR_FILE}"

echo "==> Deployment complete"
kubectl get pods -n "${NAMESPACE}" -o wide
