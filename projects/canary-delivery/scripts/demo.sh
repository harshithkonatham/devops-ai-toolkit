#!/usr/bin/env bash
# Run the whole canary demo on your machine (needs docker, kind and kubectl):
#   1. v1 is deployed
#   2. v2 (healthy) goes through the canary steps and is promoted
#   3. v3 (50% errors) is caught by the error-rate check and rolled back
#   4. v4 (400 ms slower) is caught by the latency check and rolled back
#   5. Reverting to v2 restores a healthy rollout straight away
#
# Delete the cluster afterwards with: kind delete cluster --name canary-demo
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source lib.sh

CLUSTER="${CLUSTER:-canary-demo}"
for tool in docker kind kubectl curl; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }
done

if ! kind get clusters | grep -qx "$CLUSTER"; then
  log "Creating kind cluster $CLUSTER"
  kind create cluster --name "$CLUSTER" --wait 120s
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

log "Building and loading the image"
docker build -t canary-demo:dev ..
kind load docker-image canary-demo:dev --name "$CLUSTER"

log "Installing Argo Rollouts"
./install-rollouts.sh

log "Deploying v1"
./deploy.sh

./release.sh v2
./verify-traffic.sh v2

EXPECT=Degraded ./release.sh v3 0.5
./verify-traffic.sh v2

EXPECT=Degraded ./release.sh v4 0 400
./verify-traffic.sh v2

log "Reverting to v2 (in GitOps: revert the bad commit)"
TIMEOUT=60 ./release.sh v2
./verify-traffic.sh v2

log "Demo complete: v2 promoted, v3 and v4 rolled back automatically, users stayed on v2"
