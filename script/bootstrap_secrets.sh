#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="secure-ai"
SECRET_NAME="secure-ai-backend-secret"

if kubectl get secret "${SECRET_NAME}" -n "${NAMESPACE}" &>/dev/null; then
  echo "==> Secret '${SECRET_NAME}' already exists — skipping"
  echo "    To regenerate, delete it first:"
  echo "    kubectl delete secret ${SECRET_NAME} -n ${NAMESPACE}"
  exit 0
fi

echo "==> Generating credentials"
ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
USER_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

ADMIN_HASH=$(python3 -c "import bcrypt, sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "${ADMIN_PASSWORD}")
USER_HASH=$(python3 -c "import bcrypt, sys; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "${USER_PASSWORD}")

echo "==> Ensuring namespace exists"
kubectl apply -f deploy/k8s/namespace.yaml

echo "==> Creating secret '${SECRET_NAME}'"
kubectl create secret generic "${SECRET_NAME}" \
  -n "${NAMESPACE}" \
  --from-literal=ADMIN_PASSWORD_HASH="${ADMIN_HASH}" \
  --from-literal=USER_PASSWORD_HASH="${USER_HASH}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}"

echo ""
echo "==> Done. Save these credentials — they will not be shown again:"
echo ""
echo "    Admin password: ${ADMIN_PASSWORD}"
echo "    User password:  ${USER_PASSWORD}"
echo ""
