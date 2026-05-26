#!/usr/bin/env bash
set -euo pipefail

REGISTRY="registry.lab:30500"
IMAGE_NAME="secure-ai-frontend"
IMAGE_TAG="${1:-latest}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
NAMESPACE="secure-ai"

echo "==> Building Docker image: ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" -f frontend/Dockerfile frontend/

echo "==> Pushing image to registry"
docker push "${FULL_IMAGE}"

echo "==> Applying Kubernetes manifests"
kubectl apply -f deploy/k8s/frontend/service.yaml
kubectl apply -f deploy/k8s/frontend/ingress.yaml

echo "==> Deploying image: ${FULL_IMAGE}"
sed "s|IMAGE_TAG|${IMAGE_TAG}|g" \
  deploy/k8s/frontend/deployment.yaml | kubectl apply -f -

echo "==> Restarting deployment to pick up new image"
kubectl rollout restart deployment/secure-ai-frontend -n "${NAMESPACE}"

echo "==> Waiting for rollout"
kubectl rollout status deployment secure-ai-frontend -n "${NAMESPACE}" --timeout=180s

echo "==> Deployment complete"
kubectl get pods -n "${NAMESPACE}" -o wide
