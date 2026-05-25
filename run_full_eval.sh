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

MODEL="gemma_4_31b_it"
TOKENIZER="/home/rainis/Desktop/workplace/models/google_gemma_4_31B_it"
BASE_URL_CHAT="http://127.0.0.1:18023/v1/chat/completions"
BASE_URL_V1="http://127.0.0.1:18023/v1"
export OPENAI_API_KEY="gpustack_59c26841407595f9_344d01c4b30e6c66895b76dbe134fd03"
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

run_track harness    bash "$SCRIPT_DIR/vsm/harness/run_harness.sh" "$MODEL" "$TOKENIZER" "$BASE_URL_CHAT"
run_track nlu        bash "$SCRIPT_DIR/vsm/nlu/run_nlu.sh" --model "$MODEL" --endpoint "$BASE_URL_CHAT"
run_track agent      bash "$SCRIPT_DIR/vsm/agent/run_gpustack_custom.sh" "$MODEL" "$BASE_URL_CHAT"
run_track multimodal bash "$SCRIPT_DIR/vsm/multimodal/run_all.sh" "$MODEL" "$BASE_URL_V1"

echo "[full_eval] DONE @ $(date +%H:%M:%S)" | tee -a "$LOG_DIR/_master.log"

if ((${#TRACK_FAILURES[@]} > 0)); then
  trap - INT TERM EXIT
  printf '[full_eval] FAILED TRACKS (%d): %s\n' "${#TRACK_FAILURES[@]}" "${TRACK_FAILURES[*]}" | tee -a "$LOG_DIR/_master.log" >&2
  exit 1
fi
trap - INT TERM EXIT
