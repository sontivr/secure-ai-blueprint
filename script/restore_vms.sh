#!/usr/bin/env bash
set -euo pipefail

CONTROLPLANE="controlplane"
WORKER_VMS=("node01" "node02")
ALL_VMS=("${CONTROLPLANE}" "${WORKER_VMS[@]}")

echo "==> Available snapshots:"
multipass list --snapshots
echo ""

read -r -p "Snapshot name to restore (e.g. clean-20260614-1800): " SNAPSHOT_NAME

if [[ -z "${SNAPSHOT_NAME}" ]]; then
  echo "ERROR: No snapshot name provided."
  exit 1
fi

echo ""
echo "WARNING: This will stop all VMs and restore them to snapshot '${SNAPSHOT_NAME}'."
echo "         Any cluster state since that snapshot will be lost."
echo ""
read -r -p "Proceed? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

echo ""
echo "==> Stopping all VMs"
for VM in "${ALL_VMS[@]}"; do
  echo "  --> Stopping ${VM}"
  multipass stop --force "${VM}" 2>/dev/null || true
done

echo ""
echo "==> Restoring snapshots"
for VM in "${ALL_VMS[@]}"; do
  echo "  --> Restoring ${VM} to ${SNAPSHOT_NAME}"
  multipass restore "${VM}" --snapshot "${SNAPSHOT_NAME}" --destructive
done

echo ""
echo "==> Starting all VMs"
multipass start "${CONTROLPLANE}"
for VM in "${WORKER_VMS[@]}"; do
  multipass start "${VM}"
done

echo ""
echo "==> Waiting for k3s API server"
until kubectl get nodes &>/dev/null; do sleep 5; done

echo "==> Waiting for all nodes to be Ready"
until kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" | grep -q "^3$"; do
  sleep 5
done

echo ""
echo "==> Cluster restored from snapshot '${SNAPSHOT_NAME}':"
kubectl get nodes -o wide
