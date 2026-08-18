#!/usr/bin/env bash
# 두 평가 트리의 agent/functionchat/taubench 공용 코드 동기화와 회귀 테스트를 확인한다.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE_A="$ROOT_DIR/foundation_model_test_non_thinking"
TREE_B="$ROOT_DIR/foundation_model_test_thinking"
PYTHON="$TREE_A/.venv/bin/python"
FAILED=0

tree_log() {
  echo "[tree-check] $*"
}

assert_same() {
  local label="$1"
  local left="$2"
  local right="$3"
  local output

  if output="$(diff -qr --exclude='__pycache__' --exclude='*.pyc' "$left" "$right" 2>&1)"; then
    tree_log "IDENTICAL $label"
  else
    tree_log "FAIL drift detected: $label"
    while IFS= read -r line; do
      tree_log "$line"
    done <<< "$output"
    FAILED=1
  fi
}

run_test() {
  local tree_label="$1"
  local tree_dir="$2"
  local test_path="$3"
  local output
  local rc

  tree_log "RUN $tree_label/$test_path"
  output="$(
    MODEL_TEST_BASE="$tree_dir" \
    FUNCTIONCHAT_BENCH_DIR="${FUNCTIONCHAT_BENCH_DIR:-}" \
    "$PYTHON" "$tree_dir/$test_path" 2>&1
  )"
  rc=$?
  while IFS= read -r line; do
    tree_log "$tree_label $line"
  done <<< "$output"
  tree_log "EXIT $tree_label/$test_path => $rc"
  if (( rc != 0 )); then
    FAILED=1
  fi
}

if [[ ! -x "$PYTHON" ]]; then
  tree_log "FAIL Python not found: $PYTHON"
  exit 1
fi

assert_same "shared/agent/scoring/" \
  "$TREE_A/shared/agent/scoring" \
  "$TREE_B/shared/agent/scoring"
assert_same "shared/agent/tests/test_agent_scoring.py" \
  "$TREE_A/shared/agent/tests/test_agent_scoring.py" \
  "$TREE_B/shared/agent/tests/test_agent_scoring.py"
assert_same "shared/agent/gpustack_custom/tool_call_parser.py" \
  "$TREE_A/shared/agent/gpustack_custom/tool_call_parser.py" \
  "$TREE_B/shared/agent/gpustack_custom/tool_call_parser.py"
assert_same "shared/agent/tests/test_tool_call_parser.py" \
  "$TREE_A/shared/agent/tests/test_tool_call_parser.py" \
  "$TREE_B/shared/agent/tests/test_tool_call_parser.py"
assert_same "shared/functionchat/" \
  "$TREE_A/shared/functionchat" \
  "$TREE_B/shared/functionchat"
assert_same "shared/taubench/" \
  "$TREE_A/shared/taubench" \
  "$TREE_B/shared/taubench"

for tree_label in A B; do
  if [[ "$tree_label" == "A" ]]; then
    tree_dir="$TREE_A"
  else
    tree_dir="$TREE_B"
  fi
  run_test "$tree_label" "$tree_dir" "shared/agent/tests/test_agent_scoring.py"
  run_test "$tree_label" "$tree_dir" "shared/agent/tests/test_tool_call_parser.py"
  FUNCTIONCHAT_BENCH_DIR="$TREE_A/data/FunctionChat-Bench" \
    run_test "$tree_label" "$tree_dir" "shared/functionchat/tests/test_functionchat_scoring.py"
  run_test "$tree_label" "$tree_dir" "shared/taubench/tests/test_taubench_scoring.py"
  run_test "$tree_label" "$tree_dir" "configs/tests/test_load_model_config.py"
done

if (( FAILED != 0 )); then
  tree_log "FAILED"
  exit 1
fi

tree_log "PASS"
