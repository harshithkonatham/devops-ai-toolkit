#!/usr/bin/env bash
# Apply the manifests and wait for the first version (v1) to be up.
# The first deploy of a Rollout has nothing to compare against, so it goes
# straight to 100% without canary steps.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source lib.sh

kubectl apply -k ../deploy/k8s
kubectl -n "$NS" rollout status deployment/prometheus --timeout=180s
kubectl -n "$NS" rollout status deployment/canary-demo-loadgen --timeout=120s

log "Waiting for the first version to become healthy"
result="$(wait_for_rollout "" 180)"
[[ "$result" == "Healthy" ]] || { echo "First deploy did not become healthy: $result" >&2; exit 1; }
