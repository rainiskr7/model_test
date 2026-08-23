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

# .env 는 **기본값**이지 덮어쓰기가 아니다. 호출자가 이미 export 한 값이 이긴다.
# (예전엔 무조건 source 해서, 다른 엔드포인트를 향해 export 한 키를 조용히 덮어썼다.
#  2026-08-19 에 7번 서버 런이 8번 키로 나가 401 로 죽었다.)
_CALLER_OPENAI_API_KEY="${OPENAI_API_KEY:-}"
if [ -f "$BASE_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
fi
if [ -n "$_CALLER_OPENAI_API_KEY" ]; then
  OPENAI_API_KEY="$_CALLER_OPENAI_API_KEY"
fi
unset _CALLER_OPENAI_API_KEY
export OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"
# .env 를 source 하면 셸 변수만 설정된다 — export 하지 않으면 파이썬 하위
# 프로세스가 보지 못한다. 러너가 os.environ 에서 읽으므로 반드시 내보낸다.
# (2026-08-23: 이걸 빠뜨려 외부 사용자 시뮬레이터 스모크가 키 없음으로 죽었다.)
if [ -n "${TAUBENCH_USER_API_KEY:-}" ]; then
  export TAUBENCH_USER_API_KEY
fi

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
  --mode "${TAUBENCH_MODE:-solo}"
  --request-timeout "${AGENT_REQUEST_TIMEOUT:-60}"
  --task-timeout "${AGENT_TASK_TIMEOUT:-600}"
  --max-retries "${AGENT_MAX_RETRIES:-0}"
  --max-tokens "${AGENT_MAX_TOKENS:-16384}"
  --max-concurrency "${TAUBENCH_MAX_CONCURRENCY:-1}"
  --max-steps "${TAUBENCH_MAX_STEPS:-100}"
)

# 사용자 시뮬레이터 (standard 모드 필수). 모든 후보에 **같은** 모델을 써야 비교가 성립한다.
if [ -n "${TAUBENCH_USER_MODEL:-}" ]; then
  RUN_ARGS+=(--user-model "$TAUBENCH_USER_MODEL")
fi
# 사용자 시뮬레이터를 외부 API 로 보낼 때만. 키는 여기서 넘기지 않는다 —
# 프로세스 목록 노출을 피하려고 러너가 TAUBENCH_USER_API_KEY 환경변수(.env)를 직접 읽는다.
if [ -n "${TAUBENCH_USER_BASE_URL:-}" ]; then
  RUN_ARGS+=(--user-base-url "$TAUBENCH_USER_BASE_URL")
fi

"$TAU_PY" "$SCRIPT_DIR/runner/run_taubench.py" "${RUN_ARGS[@]}"
"$TAU_PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$RUN_TIMESTAMP" \
  --track "$TRACK_NAME"
