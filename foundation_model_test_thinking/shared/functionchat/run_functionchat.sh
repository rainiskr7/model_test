#!/bin/bash
# FunctionChat exact-match 트랙. Agent harness와 같은 AGENT_* 실행 환경 계약을 쓴다.
# Usage: ./run_functionchat.sh MODEL [BASE_URL]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
export MODEL_TEST_BASE="$BASE_DIR"

MODEL="${1:?MODEL required: ./run_functionchat.sh MODEL [BASE_URL]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
TRACK_NAME="${AGENT_TRACK_NAME:-functionchat}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

if [ -f "$BASE_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
fi
export OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"

if [ ! -d "$BASE_DIR/data/FunctionChat-Bench" ]; then
  echo "ERROR: $BASE_DIR/data/FunctionChat-Bench 없음. 먼저 install.sh 실행." >&2
  exit 1
fi

RUN_ARGS=(
  --model "$MODEL"
  --base-url "$BASE_URL"
  --track-name "$TRACK_NAME"
)
if [ -n "${AGENT_REQUEST_TIMEOUT:-}" ]; then
  RUN_ARGS+=(--request-timeout "$AGENT_REQUEST_TIMEOUT")
fi
if [ -n "${AGENT_TASK_TIMEOUT:-}" ]; then
  RUN_ARGS+=(--task-timeout "$AGENT_TASK_TIMEOUT")
fi
if [ -n "${AGENT_MAX_RETRIES:-}" ]; then
  RUN_ARGS+=(--max-retries "$AGENT_MAX_RETRIES")
fi
if [ -n "${AGENT_MAX_TOKENS:-}" ]; then
  RUN_ARGS+=(--max-tokens "$AGENT_MAX_TOKENS")
fi

RUN_TIMESTAMP="${EVAL_TIMESTAMP:-}"
if [ -z "$RUN_TIMESTAMP" ] && [ -f "$BASE_DIR/.eval_session" ]; then
  RUN_TIMESTAMP="$(cat "$BASE_DIR/.eval_session")"
fi
if [ -z "$RUN_TIMESTAMP" ]; then
  RUN_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
fi
export EVAL_TIMESTAMP="$RUN_TIMESTAMP"

"$PY" "$SCRIPT_DIR/runner/run_functionchat.py" "${RUN_ARGS[@]}"

"$PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$RUN_TIMESTAMP" \
  --track "$TRACK_NAME"
