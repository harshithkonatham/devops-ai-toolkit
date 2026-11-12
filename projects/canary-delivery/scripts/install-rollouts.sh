#!/usr/bin/env bash
# Install the Argo Rollouts controller, after checking the manifest's checksum.
set -euo pipefail
cd "$(dirname "$0")"

ROLLOUTS_VERSION="${ROLLOUTS_VERSION:-v1.10.2}"
# sha256 of install.yaml for the version above. Update both together.
ROLLOUTS_SHA256="${ROLLOUTS_SHA256:-b8280994791eaee7eb91c8b84450efcc6e0292fca5aafc18c1b0ebc5d18dbefe}"

manifest="$(mktemp)"
trap 'rm -f "$manifest"' EXIT

echo "Downloading Argo Rollouts $ROLLOUTS_VERSION"
curl -sSfL --retry 3 -o "$manifest" \
  "https://github.com/argoproj/argo-rollouts/releases/download/${ROLLOUTS_VERSION}/install.yaml"
echo "${ROLLOUTS_SHA256}  ${manifest}" | sha256sum -c - 2>/dev/null \
  || echo "${ROLLOUTS_SHA256}  ${manifest}" | shasum -a 256 -c -

kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
# Server-side apply: the CRDs are too large for client-side apply's annotation.
kubectl apply --server-side -n argo-rollouts -f "$manifest"
kubectl -n argo-rollouts rollout status deployment/argo-rollouts --timeout=180s
