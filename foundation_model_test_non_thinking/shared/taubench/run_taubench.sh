#!/bin/bash
# tau2-bench no-user 트랙. Agent harness와 같은 AGENT_* 실행 환경 계약을 쓴다.
# Usage: ./run_taubench.sh MODEL [BASE_URL]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
export MODEL_TEST_BASE="$BASE_DIR"

MODEL="${1:?MODEL required: ./run_taubench.sh MODEL [BASE_URL]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
TRACK_NAME="${AGENT_TRACK_NAME:-taubench}"
TAU_PY="${TAU_PY:-$BASE_DIR/.venv-taubench/bin/python}"

if [ -f "$BASE_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
fi
export OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"

if [ ! -x "$TAU_PY" ]; then
  echo "ERROR: isolated tau2 venv 없음: $TAU_PY. 먼저 install.sh 실행." >&2
  exit 1
fi
if [ ! -d "$BASE_DIR/data/tau2-bench" ]; then
  echo "ERROR: $BASE_DIR/data/tau2-bench 없음. 먼저 install.sh 실행." >&2
  exit 1
fi

RUN_TIMESTAMP="${EVAL_TIMESTAMP:-}"
if [ -z "$RUN_TIMESTAMP" ] && [ -f "$BASE_DIR/.eval_session" ]; then
  RUN_TIMESTAMP="$(cat "$BASE_DIR/.eval_session")"
fi
if [ -z "$RUN_TIMESTAMP" ]; then
  RUN_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
fi
export EVAL_TIMESTAMP="$RUN_TIMESTAMP"

RUN_ARGS=(
  --model "$MODEL"
  --base-url "$BASE_URL"
  --track-name "$TRACK_NAME"
  --split "${TAUBENCH_SPLIT:-test}"
  --request-timeout "${AGENT_REQUEST_TIMEOUT:-60}"
  --task-timeout "${AGENT_TASK_TIMEOUT:-600}"
  --max-retries "${AGENT_MAX_RETRIES:-0}"
  --max-tokens "${AGENT_MAX_TOKENS:-16384}"
  --max-concurrency "${TAUBENCH_MAX_CONCURRENCY:-1}"
  --max-steps "${TAUBENCH_MAX_STEPS:-100}"
)

"$TAU_PY" "$SCRIPT_DIR/runner/run_taubench.py" "${RUN_ARGS[@]}"
"$TAU_PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$RUN_TIMESTAMP" \
  --track "$TRACK_NAME"
