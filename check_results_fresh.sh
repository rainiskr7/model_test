#!/usr/bin/env bash
# 두 평가 트리에 커밋된 summary.json이 현재 채점 코드와 일치하는지 확인한다.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE_A="$ROOT_DIR/foundation_model_test_non_thinking"
TREE_B="$ROOT_DIR/foundation_model_test_thinking"
PYTHON="$TREE_A/.venv/bin/python"
TOTAL=0
PASSED=0
DRIFTED=0
ERRORS=0
UNSCORED=0

results_log() {
  echo "[results-fresh] $*"
}

report_details() {
  local output="$1"
  local line

  while IFS= read -r line; do
    case "$line" in
      *"[agent-scoring] DRIFT"*|*"[agent-scoring] error:"*)
        results_log "$line"
        ;;
    esac
  done <<< "$output"
}

check_tree() {
  local tree_label="$1"
  local tree_dir="$2"
  local level_path
  local results_dir
  local previous_results_dir=""
  local relative_dir
  local output
  local rc
  local -a level_files

  if ! compgen -G "$tree_dir/results/*/*/language/*/L*.json" > /dev/null; then
    return
  fi

  level_files=("$tree_dir"/results/*/*/language/*/L*.json)

  for level_path in "${level_files[@]}"; do
    results_dir="$(dirname "$level_path")"
    if [[ "$results_dir" == "$previous_results_dir" ]]; then
      continue
    fi
    previous_results_dir="$results_dir"
    relative_dir="${results_dir#"$ROOT_DIR/"}"
    TOTAL=$((TOTAL + 1))

    if [[ ! -f "$results_dir/summary.json" ]]; then
      UNSCORED=$((UNSCORED + 1))
      results_log "UNSCORED $tree_label $relative_dir"
      continue
    fi

    output="$(
      MODEL_TEST_BASE="$tree_dir" \
        "$PYTHON" "$tree_dir/shared/agent/scoring/score_run.py" \
        --results-dir "$results_dir" --check 2>&1
    )"
    rc=$?

    if (( rc == 0 )); then
      PASSED=$((PASSED + 1))
      results_log "PASS $tree_label $relative_dir"
    elif (( rc == 1 )); then
      DRIFTED=$((DRIFTED + 1))
      results_log "DRIFT $tree_label $relative_dir"
      report_details "$output"
    else
      ERRORS=$((ERRORS + 1))
      results_log "ERROR $tree_label $relative_dir (check error, exit=$rc)"
      report_details "$output"
    fi
  done
}

if [[ ! -x "$PYTHON" ]]; then
  results_log "FAIL Python not found: $PYTHON"
  exit 1
fi

check_tree "A" "$TREE_A"
check_tree "B" "$TREE_B"

if (( UNSCORED != 0 )); then
  results_log "NOTE legacy pre-harness-fix runs are intentionally left unscored because they lack native_tool_calling and the fields current metrics require, so their numbers would not be comparable."
fi

if (( DRIFTED != 0 || ERRORS != 0 )); then
  results_log "SUMMARY total=$TOTAL pass=$PASSED drift=$DRIFTED unscored=$UNSCORED errors=$ERRORS status=FAIL"
  exit 1
fi

results_log "SUMMARY total=$TOTAL pass=$PASSED drift=$DRIFTED unscored=$UNSCORED errors=$ERRORS status=PASS"
