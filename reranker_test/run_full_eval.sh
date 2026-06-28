#!/bin/bash
# reranker 클래스 전체 트랙 순차 실행 — 참조 model_test/run_full_eval.sh 패턴.
# Usage: ./run_full_eval.sh <model_config_name>      # 예: ./run_full_eval.sh bge-reranker-v2-m3
# 결과: results/<safe_model>/<EVAL_TIMESTAMP>/reranker/<track>/<bench>/summary.json
# 로그: logs/<EVAL_TIMESTAMP>/<track>.log

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# venv 활성화(있으면)
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.venv/bin/activate"
fi
export MODEL_TEST_BASE="$SCRIPT_DIR"

# 첫 인자 = 모델 config 명(configs/models/<NAME>.yaml). 미지정 시 목록 안내.
if [ -z "${1:-}" ]; then
  echo "Usage: $0 <model_config_name>" >&2
  echo "사용 가능:" >&2
  ls "$SCRIPT_DIR/configs/models/" 2>/dev/null | sed 's/\.yaml$//' | sed 's/^/  /' >&2
  exit 2
fi
MODEL_CONFIG="$1"

# yaml → env (KEY, MODEL, MODEL_ID, MODEL_CLASS, BACKEND, BASE_URL, TRACKS)
# (loader 가 파일명 stem == yaml key 를 강제하므로 run.py --rerankers KEY 와 config.py 로딩이 일치)
# shellcheck disable=SC1090
source <(python3 "$SCRIPT_DIR/configs/load_model_config.py" "$MODEL_CONFIG") || exit 1
echo "[full_eval] config=$MODEL_CONFIG → KEY=$KEY MODEL=$MODEL BACKEND=$BACKEND"

# 세션 타임스탬프(.eval_session). 없으면 즉석 생성 후 기록(이번 런만 유효).
if [ ! -f "$SCRIPT_DIR/.eval_session" ]; then
  date +%Y%m%d_%H%M%S > "$SCRIPT_DIR/.eval_session"
  echo "[full_eval] WARN: 활성 세션 없음 → 즉석 세션 생성($(cat "$SCRIPT_DIR/.eval_session"))"
fi
export EVAL_TIMESTAMP="$(cat "$SCRIPT_DIR/.eval_session")"

# endpoint backend 면 preflight(서버 응답 + MODEL_ID 존재 확인)
if [ "$BACKEND" = "endpoint" ]; then
  if [ -f "$SCRIPT_DIR/.env" ]; then source "$SCRIPT_DIR/.env"; fi
  : "${OPENAI_API_KEY:?endpoint backend 는 OPENAI_API_KEY 필요(.env 작성 또는 export)}"
  export OPENAI_API_KEY
  echo "[full_eval] endpoint preflight: $BASE_URL/models (model_id=$MODEL_ID)"
  PF=$(curl -s --max-time 5 -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL/models" 2>/dev/null) || {
    echo "[full_eval] ERROR: endpoint 응답 없음($BASE_URL/models). 서빙 확인." >&2; exit 1; }
  echo "$PF" | MODEL_ID="$MODEL_ID" python3 -c "
import json, os, sys
try: d = json.loads(sys.stdin.read())
except Exception as e: sys.exit(f'preflight JSON parse 실패: {e}')
ids = [m.get('id') for m in d.get('data', [])]
mid = os.environ['MODEL_ID']
if mid not in ids:
    sys.exit(f'MODEL_ID={mid} 가 endpoint 응답에 없음. 사용 가능: {ids}')
print(f'[full_eval] preflight OK: {mid} 응답 확인')
" || { echo '[full_eval] ERROR: endpoint preflight 실패(모델 id 불일치).' >&2; exit 1; }
fi

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
  return 0   # 트랙 실패해도 다음 진행(CONVENTIONS §6)
}

echo "[full_eval] EVAL_TIMESTAMP=$EVAL_TIMESTAMP MODEL=$MODEL" | tee "$LOG_DIR/_master.log"

for track in $TRACKS; do
  case "$track" in
    native)
      run_track native  python3 run.py native  --rerankers "$KEY" ;;
    rerank)
      run_track rerank  python3 run.py rerank  --rerankers "$KEY" ;;
    latency)
      run_track latency python3 run.py latency --rerankers "$KEY" ;;
    *) echo "[full_eval] WARN: unknown track '$track' (configs/models/$MODEL_CONFIG.yaml)" ;;
  esac
done

# 결과 매트릭스 정리(전 모델 합산 — 마지막 1회)
run_track aggregate python3 run.py aggregate

echo "[full_eval] DONE @ $(date +%H:%M:%S)" | tee -a "$LOG_DIR/_master.log"
if ((${#TRACK_FAILURES[@]} > 0)); then
  printf '[full_eval] FAILED TRACKS (%d): %s\n' "${#TRACK_FAILURES[@]}" "${TRACK_FAILURES[*]}" \
    | tee -a "$LOG_DIR/_master.log" >&2
  exit 1
fi
