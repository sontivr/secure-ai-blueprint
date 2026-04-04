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
kubectl rollout status deployment secure-ai-backend --timeout=180s

echo "==> Cleaning transferred tar from controlplane"
multipass exec "${CONTROLPLANE_VM}" -- rm -f "/home/ubuntu/${TAR_FILE}"

echo "==> Deployment complete"
kubectl get pods -o wide
