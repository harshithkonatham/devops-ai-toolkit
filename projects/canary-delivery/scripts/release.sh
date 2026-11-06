#!/usr/bin/env bash
# Ship a new "release" by changing the Rollout's pod template, then wait for
# Argo Rollouts to promote or abort it.
#
#   scripts/release.sh VERSION [ERROR_RATE] [LATENCY_MS]
#
# Set EXPECT=Healthy (default) or EXPECT=Degraded to fail the script if the
# result differs. Examples:
#   scripts/release.sh v2                        # good release, promoted
#   EXPECT=Degraded scripts/release.sh v3 0.5    # 50% errors, rolled back
#
# In a GitOps setup this change would be a commit to rollout.yaml that Argo CD
# syncs. The patch here does the same thing without a git server.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source lib.sh

version="${1:?usage: release.sh VERSION [ERROR_RATE] [LATENCY_MS]}"
error_rate="${2:-0}"
latency_ms="${3:-0}"
expect="${EXPECT:-Healthy}"
timeout="${TIMEOUT:-300}"

before="$(rollout_field .status.currentPodHash)"
log "Releasing $version (ERROR_RATE=$error_rate, LATENCY_MS=$latency_ms), expecting $expect"

patch="$(printf '[{"op":"replace","path":"/spec/template/spec/containers/0/env","value":[
  {"name":"VERSION","value":"%s"},
  {"name":"ERROR_RATE","value":"%s"},
  {"name":"LATENCY_MS","value":"%s"}]}]' "$version" "$error_rate" "$latency_ms")"
out="$(kubectl -n "$NS" patch rollout "$ROLLOUT" --type json -p "$patch")"
echo "$out"
if [[ "$out" == *"(no change)"* ]]; then
  echo "That release is already running; nothing to do."
  exit 0
fi

result="$(wait_for_rollout "$before" "$timeout")" || true
show_last_analysis
if [[ "$result" != "$expect" ]]; then
  echo "FAIL: release $version ended as $result, expected $expect" >&2
  exit 1
fi
echo "OK: release $version ended as $result, as expected"
