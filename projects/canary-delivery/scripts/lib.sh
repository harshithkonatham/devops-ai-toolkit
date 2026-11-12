# Shared helpers. Sourced by the other scripts, not run directly.
# shellcheck shell=bash

NS="${NS:-canary-demo}"
ROLLOUT="${ROLLOUT:-canary-demo}"

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

rollout_field() {
  kubectl -n "$NS" get rollout "$ROLLOUT" -o "jsonpath={$1}" 2>/dev/null || true
}

# Wait until the rollout has finished with a pod template other than $1.
# Prints the final phase: Healthy (promoted) or Degraded (aborted).
#   $1  pod-template hash before the change ("" for the first deploy)
#   $2  timeout in seconds
wait_for_rollout() {
  local before="$1" deadline=$((SECONDS + $2)) hash stable phase step message
  while ((SECONDS < deadline)); do
    hash="$(rollout_field .status.currentPodHash)"
    stable="$(rollout_field .status.stableRS)"
    phase="$(rollout_field .status.phase)"
    step="$(rollout_field .status.currentStepIndex)"
    message="$(rollout_field .status.message)"
    printf '   phase=%-11s step=%-2s canary=%-10s stable=%-10s %s\n' \
      "$phase" "${step:--}" "$hash" "$stable" "$message" >&2
    if [[ -n "$hash" && "$hash" != "$before" ]]; then
      # Healthy only counts once the new version is also the stable one.
      if [[ "$phase" == "Healthy" && "$stable" == "$hash" ]]; then echo Healthy; return 0; fi
      if [[ "$phase" == "Degraded" ]]; then echo Degraded; return 0; fi
    fi
    sleep 5
  done
  echo Timeout
  return 1
}

# Show the most recent canary analysis and its measurements.
show_last_analysis() {
  local run
  run="$(kubectl -n "$NS" get analysisrun --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null || true)"
  [[ -z "$run" ]] && { echo "   (no analysis runs yet)"; return 0; }
  echo "   AnalysisRun $run: $(kubectl -n "$NS" get analysisrun "$run" -o jsonpath='{.status.phase}')"
  kubectl -n "$NS" get analysisrun "$run" -o jsonpath='{range .status.metricResults[*]}{"   - "}{.name}{": "}{.phase}{" (ok "}{.successful}{", failed "}{.failed}{", errors "}{.consecutiveError}{") last value "}{.measurements[-1:].value}{"\n"}{end}'
}
