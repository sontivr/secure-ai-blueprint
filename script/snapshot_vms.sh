#!/usr/bin/env bash
set -euo pipefail

CONTROLPLANE="controlplane"
WORKER_VMS=("node01" "node02")
SNAPSHOT_NAME="clean-$(date +%Y%m%d-%H%M)"

echo "==> Verifying cluster health before snapshotting"
READY_NODES=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" || true)
if [[ "${READY_NODES}" -lt 3 ]]; then
  echo "ERROR: Only ${READY_NODES}/3 nodes are Ready — fix cluster before snapshotting"
  exit 1
fi
echo "    All 3 nodes Ready"

echo ""
echo "==> Snapshot name: ${SNAPSHOT_NAME}"
echo "    This will stop each VM, snapshot it, then restart it."
echo "    The cluster will be unavailable for ~2-3 minutes per node."
echo ""
read -r -p "Proceed? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

snapshot_worker() {
  local VM="$1"

  echo ""
  echo "==> Snapshotting ${VM}"
  echo "  --> Stopping k3s-agent"
  multipass exec "${VM}" -- sudo systemctl stop k3s-agent

  echo "  --> Stopping VM"
  multipass stop "${VM}"

  echo "  --> Taking snapshot: ${SNAPSHOT_NAME}"
  multipass snapshot "${VM}" --name "${SNAPSHOT_NAME}" --comment "Clean cluster state"

  echo "  --> Starting VM"
  multipass start "${VM}"

  echo "  --> Waiting for k3s-agent to be active"
  until multipass exec "${VM}" -- sudo systemctl is-active k3s-agent 2>/dev/null | grep -q "^active$"; do
    sleep 3
  done
  echo "  --> ${VM} ready"
}

backup_controlplane() {
  local BACKUP_DIR="${HOME}/.secure-ai-backups/${SNAPSHOT_NAME}"
  mkdir -p "${BACKUP_DIR}"

  echo ""
  echo "==> Backing up controlplane (QEMU snapshot unsupported for >32GB disks)"

  echo "  --> Saving k3s token"
  multipass exec "${CONTROLPLANE}" -- sudo cat /var/lib/rancher/k3s/server/node-token \
    > "${BACKUP_DIR}/node-token"

  echo "  --> Triggering etcd snapshot"
  multipass exec "${CONTROLPLANE}" -- sudo k3s etcd-snapshot save \
    --name "${SNAPSHOT_NAME}" 2>/dev/null || true

  echo "  --> Copying etcd snapshot"
  SNAPSHOT_FILE=$(multipass exec "${CONTROLPLANE}" -- sudo ls -t \
    /var/lib/rancher/k3s/server/db/snapshots/ 2>/dev/null | head -1)
  if [[ -n "${SNAPSHOT_FILE}" ]]; then
    multipass exec "${CONTROLPLANE}" -- sudo cat \
      "/var/lib/rancher/k3s/server/db/snapshots/${SNAPSHOT_FILE}" \
      > "${BACKUP_DIR}/etcd-${SNAPSHOT_FILE}"
    echo "  --> Saved etcd snapshot: ${SNAPSHOT_FILE}"
  fi

  echo "  --> Controlplane backup saved to: ${BACKUP_DIR}"
}

for VM in "${WORKER_VMS[@]}"; do
  snapshot_worker "${VM}"
done

backup_controlplane

echo ""
echo "==> Waiting for all nodes to be Ready"
until kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" | grep -q "^3$"; do
  sleep 5
done

echo ""
echo "==> Snapshots complete:"
multipass list --snapshots
echo ""
echo "==> Controlplane backups:"
ls -lh "${HOME}/.secure-ai-backups/${SNAPSHOT_NAME}/"
