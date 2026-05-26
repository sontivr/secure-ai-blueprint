#!/usr/bin/env bash
set -euo pipefail

REGISTRY="registry.lab:30500"
IMAGE_NAME="secure-ai-backend"
IMAGE_TAG="${1:-latest}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
NAMESPACE="secure-ai"

echo "==> Building Docker image: ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" -f Dockerfile.backend .

echo "==> Pushing image to registry"
docker push "${FULL_IMAGE}"

echo "==> Ensuring namespace exists"
kubectl apply -f deploy/k8s/namespace.yaml

echo "==> Applying Kubernetes manifests"
kubectl apply -f deploy/k8s/backend/pvc.yaml
kubectl apply -f deploy/k8s/backend/service.yaml
kubectl apply -f deploy/k8s/backend/ingress.yaml

echo "==> Deploying image: ${FULL_IMAGE}"
sed "s|secure-ai-backend:IMAGE_TAG|${REGISTRY}/secure-ai-backend:${IMAGE_TAG}|g" \
  deploy/k8s/backend/deployment.yaml | kubectl apply -f -

echo "==> Restarting deployment to pick up new image"
kubectl rollout restart deployment/secure-ai-backend -n "${NAMESPACE}"

echo "==> Waiting for rollout"
kubectl rollout status deployment secure-ai-backend -n "${NAMESPACE}" --timeout=180s

echo "==> Deployment complete"
kubectl get pods -n "${NAMESPACE}" -o wide
