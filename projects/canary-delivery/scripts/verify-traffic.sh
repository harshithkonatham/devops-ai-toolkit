#!/usr/bin/env bash
# Check that every request through the Service is served by one version.
# Sampled from inside the cluster (kubectl port-forward would pin a single pod).
#
#   scripts/verify-traffic.sh EXPECTED_VERSION
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source lib.sh

expected="${1:?usage: verify-traffic.sh EXPECTED_VERSION}"
count="${COUNT:-50}"

log "Checking that users are served only by $expected"
# Retry briefly: an aborted canary's pods can take a few seconds to leave the Service.
for _ in $(seq 1 12); do
  counts="$(kubectl -n "$NS" exec deployment/canary-demo-loadgen -- \
    python -m canary_demo.loadgen sample --url http://canary-demo/ --count "$count")"
  echo "   $count requests served by: $counts"
  if [[ "$counts" == "{\"$expected\": $count}" ]]; then
    echo "OK: all traffic is on $expected"
    exit 0
  fi
  sleep 5
done
echo "FAIL: traffic is not all on $expected" >&2
exit 1
