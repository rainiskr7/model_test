#!/bin/bash
# vsm 클래스 전체 트랙 순차 실행 (gemma_4_26b_a4b_it)
# Logs: logs/<EVAL_TIMESTAMP>/<track>.log

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 부모 죽으면 자식까지 일괄 cleanup
# (이전 run 에서 wrapper 죽은 뒤 ko-agentbench 자식이 살아남아 결과 폴더 오염시킨 사례 있음)
# 자기 자신을 setsid 로 재실행해 새 session leader 가 되게 만든 뒤,
# trap 에서 같은 session 의 모든 process 를 process group kill 로 일괄 종료.
if [ -z "${_FULL_EVAL_REEXEC:-}" ]; then
  export _FULL_EVAL_REEXEC=1
  exec setsid -w bash "$0" "$@"
fi
PGID="$(ps -o pgid= $$ | tr -d ' ')"
cleanup() {
  local sig="${1:-EXIT}"
  trap - INT TERM EXIT  # 재진입 방지
  echo "[full_eval] trap: cleanup pgid=$PGID sig=$sig" | tee -a "${LOG_DIR:-/tmp}/_master.log" 2>/dev/null
  # 자기 자신($$)을 제외한 process group 멤버에만 시그널 → trap 함수가 KILL 라인까지 도달 보장.
  local victims
  victims=$(pgrep -g "$PGID" 2>/dev/null | awk -v self="$$" '$0 != self { print }' | tr '\n' ' ')
  if [ -n "$victims" ]; then
    # 1) 직속 + 손자 SIGTERM
    kill -TERM $victims 2>/dev/null || true
    sleep 2
    # 2) 살아남은 것들 SIGKILL
    victims=$(pgrep -g "$PGID" 2>/dev/null | awk -v self="$$" '$0 != self { print }' | tr '\n' ' ')
    [ -n "$victims" ] && kill -KILL $victims 2>/dev/null || true
  fi
  # bash trap 은 함수가 정상 반환해도 SIGINT/SIGTERM 의 default action 을 자동 재적용하지 않음.
  # 종료 코드를 명시적으로 표준값으로 맞춤.
  case "$sig" in
    INT)  exit 130 ;;
    TERM) exit 143 ;;
  esac
}
trap 'cleanup INT'  INT
trap 'cleanup TERM' TERM
trap 'cleanup EXIT' EXIT

# venv 활성화 (lm_eval, python 등이 PATH 에 잡혀야 함)
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"
export MODEL_TEST_BASE="$SCRIPT_DIR"

# 첫 인자 = 모델 config 명 (configs/models/<NAME>.yaml). 미지정 시 사용 가능 목록 안내.
if [ -z "${1:-}" ]; then
  echo "Usage: $0 <model_config_name>" >&2
  echo "사용 가능:" >&2
  ls "$SCRIPT_DIR/configs/models/" 2>/dev/null | sed 's/\.yaml$//' | sed 's/^/  /' >&2
  exit 2
fi
MODEL_CONFIG="$1"

# yaml → env 변수 (MODEL, TOKENIZER, MODEL_CLASS, BASE_URL_CHAT, BASE_URL_V1, TRACKS)
# shellcheck disable=SC1090
CONFIG_SHELL="$(python "$SCRIPT_DIR/configs/load_model_config.py" "$MODEL_CONFIG")" || exit $?
source <(printf '%s\n' "$CONFIG_SHELL")
unset CONFIG_SHELL
echo "[full_eval] config=$MODEL_CONFIG → MODEL=$MODEL CLASS=$MODEL_CLASS"

# API key 외부화: .env 파일 또는 env 변수에서 로드 (하드코딩 금지)
# .env 파일은 .gitignore 됨 — `OPENAI_API_KEY=gpustack_...` 형식
if [ -f "$SCRIPT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
fi
: "${OPENAI_API_KEY:?OPENAI_API_KEY 필요 (.env 파일 작성 또는 env 변수 export)}"
export OPENAI_API_KEY

# vllm preflight: 서버 살아있고 MODEL 명 일치하는지 검증
# 미일치 시 평가 시작 후 모든 트랙이 404 로 실패하는 시간 낭비 방지
echo "[full_eval] vllm preflight: $BASE_URL_V1/models"
PREFLIGHT_MODELS=$(curl -s --max-time 5 -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models" 2>/dev/null) || {
  echo "[full_eval] ERROR: vllm endpoint 응답 없음 ($BASE_URL_V1/models). vllm 서빙 중인지 확인하세요." >&2
  exit 1
}
if ! echo "$PREFLIGHT_MODELS" | python3 -c "
import json, sys
try: d = json.loads(sys.stdin.read())
except Exception as e: sys.exit(f'JSON parse 실패: {e}')
ids = [m['id'] for m in d.get('data', [])]
if '$MODEL' not in ids:
    sys.exit(f'MODEL=$MODEL 가 vllm 응답에 없음. 사용 가능: {ids}')
print(f'[full_eval] preflight OK: MODEL=$MODEL 응답 확인')
"; then
  echo "[full_eval] ERROR: vllm preflight 실패. --served-model-name $MODEL 로 띄워야 합니다." >&2
  exit 1
fi

export EVAL_TIMESTAMP="$(cat .eval_session)"

# harness 동시성 (run_harness.sh 의 num_concurrent)
export NUM_CONCURRENT="${NUM_CONCURRENT:-8}"

LOG_DIR="logs/${EVAL_TIMESTAMP}"
mkdir -p "$LOG_DIR"

TRACK_FAILURES=()

run_track() {
  local NAME="$1"; shift
  local LOG="$LOG_DIR/${NAME}.log"
  echo "[$(date +%H:%M:%S)] === ${NAME} 시작 ===" | tee -a "$LOG_DIR/_master.log"
  echo "  CMD: $*" | tee -a "$LOG_DIR/_master.log"
  ( "$@" ) >>"$LOG" 2>&1
  local RC=$?
  if (( RC != 0 )); then
    TRACK_FAILURES+=("${NAME}(rc=${RC})")
    echo "[$(date +%H:%M:%S)] === ${NAME} 실패 (rc=$RC) ===" | tee -a "$LOG_DIR/_master.log"
  else
    echo "[$(date +%H:%M:%S)] === ${NAME} 종료 (rc=$RC) ===" | tee -a "$LOG_DIR/_master.log"
  fi
  # 트랙 실패해도 다음 트랙은 계속 진행 → 호출 측에는 항상 성공 반환
  return 0
}

echo "[full_eval] EVAL_TIMESTAMP=$EVAL_TIMESTAMP" | tee "$LOG_DIR/_master.log"
echo "[full_eval] MODEL=$MODEL" | tee -a "$LOG_DIR/_master.log"
echo "[full_eval] NUM_CONCURRENT=$NUM_CONCURRENT" | tee -a "$LOG_DIR/_master.log"
echo "[full_eval] PID=$$ PGID=$PGID" | tee -a "$LOG_DIR/_master.log"

# TRACK 호출 — yaml 의 tracks 목록 + MODEL_CLASS 기반 path
# (shared/ symlink 덕에 클래스 path 가 같은 실체를 가리킴)
TRACK_BASE="$SCRIPT_DIR/$MODEL_CLASS"
for track in $TRACKS; do
  case "$track" in
    harness)    run_track harness    bash "$TRACK_BASE/harness/run_harness.sh" "$MODEL" "$TOKENIZER" "$BASE_URL_CHAT" ;;
    nlu)        run_track nlu        bash "$TRACK_BASE/nlu/run_nlu.sh" --model "$MODEL" --endpoint "$BASE_URL_CHAT" ;;
    agent)      run_track agent      bash "$TRACK_BASE/agent/run_gpustack_custom.sh" "$MODEL" "$BASE_URL_CHAT" ;;
    multimodal) run_track multimodal bash "$TRACK_BASE/multimodal/run_all.sh" "$MODEL" "$BASE_URL_V1" ;;
    *) echo "[full_eval] WARN: unknown track '$track' (configs/models/$MODEL_CONFIG.yaml)" ;;
  esac
done

echo "[full_eval] DONE @ $(date +%H:%M:%S)" | tee -a "$LOG_DIR/_master.log"

if ((${#TRACK_FAILURES[@]} > 0)); then
  trap - INT TERM EXIT
  printf '[full_eval] FAILED TRACKS (%d): %s\n' "${#TRACK_FAILURES[@]}" "${TRACK_FAILURES[*]}" | tee -a "$LOG_DIR/_master.log" >&2
  exit 1
fi
trap - INT TERM EXIT
