#!/bin/bash
# KOFFVQA — 자체 runner (KOFFVQA generate.py 우회) + 선택적 judge
#
# Source: https://github.com/maum-ai/KOFFVQA (데이터셋만 활용)
#
# 동작:
#   1. data/KOFFVQA/data/KOFFVQA.tsv 사용 (없으면 HF 에서 자동 다운로드)
#   2. 자체 runner (koffvqa_run.py) 로 OpenAI-compat API 호출 → 응답 생성
#   3. KOFFVQA-format xlsx 저장
#   4. (선택) judge 채점:
#      a) 로컬 KOFFVQA evaluate.py — local Gemma2-9B 등 GPU judge
#      b) API judge (koffvqa_api_judge.py) — 외부 OpenAI-compat judge
#
# Usage:
#   # (1) 응답 생성만
#   ./run_koffvqa.sh MODEL [BASE_URL]
#
#   # (2) API judge 까지 (외부 judge 모델 환경변수)
#   API_JUDGE=1 \
#     JUDGE_MODEL=openai/gpt-4o-mini \
#     JUDGE_BASE_URL=https://api.openai.com/v1 \
#     JUDGE_API_KEY=sk-... \
#     ./run_koffvqa.sh MODEL [BASE_URL]
#
#   # (3) 로컬 KOFFVQA evaluate.py 사용 (LOCAL_JUDGE=1, judge GPU 별도 필요)
#   LOCAL_JUDGE=1 JUDGE_MODEL=google/gemma-2-9b-it ./run_koffvqa.sh MODEL [BASE_URL]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

MODEL="${1:?'MODEL required: ./run_koffvqa.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

# 경로 해석에 쓸 인터프리터를 먼저 정한다. bare `python` 은 이 저장소의
# 실행 환경(macOS·리눅스 모두)에 없을 수 있고, 없으면 DEST 를 만들기도 전에
# 스크립트가 죽는다.
PY="${PY:-}"
if [ -z "$PY" ]; then
  for candidate in "$BASE_DIR/.venv/bin/python" python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  done
fi
[ -n "$PY" ] || { echo "[koffvqa] python 인터프리터를 찾지 못함 — 중단"; exit 1; }

# Linux에서도 기존 git 경로의 실제 casing을 재사용한다. 문자열 치환으로 따로
# 계산하면 macOS(대소문자 무시)에서는 같은 디렉토리를 가리키지만 리눅스에서는
# Python 러너가 쓰는 경로와 갈라져 산출물이 두 디렉토리로 흩어진다.
SAFE_MODEL="$("$PY" - "$SCRIPT_DIR/benches" "$BASE_DIR" "$MODEL" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from paths import results_model_dir_name
print(results_model_dir_name(sys.argv[2], sys.argv[3]))
PYEOF
)" || { echo "[koffvqa] results 모델 경로 해석 실패 — 중단"; exit 1; }

# Timestamp 결정: EVAL_TIMESTAMP env > .eval_session 파일 > 새로 생성 + 저장
if [ -n "${EVAL_TIMESTAMP:-}" ]; then
  TIMESTAMP="$EVAL_TIMESTAMP"
elif [ -f "$BASE_DIR/.eval_session" ]; then
  TIMESTAMP="$(cat "$BASE_DIR/.eval_session")"
else
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
  echo "$TIMESTAMP" > "$BASE_DIR/.eval_session"
  echo "[eval_session] 새 세션 생성: $TIMESTAMP"
fi
DEST="$BASE_DIR/results/$SAFE_MODEL/$TIMESTAMP/vision/multimodal/koffvqa"
mkdir -p "$DEST"

echo "[koffvqa] BASE=$BASE_DIR"
echo "[koffvqa] DEST=$DEST"
echo "[koffvqa] MODEL=$MODEL"

# 재현용 메타데이터
"$PY" "$SCRIPT_DIR/benches/common.py" \
  --out "$DEST/run_config.json" \
  --benchmark "KOFFVQA" \
  --model "$MODEL" \
  --base-url "$BASE_URL" \
  --repo-dir "$BASE_DIR/data/KOFFVQA" || { echo "[koffvqa] run_config 작성 실패 — 중단"; exit 1; }

# 1) 자체 runner — 응답 생성
# KOFFVQA_TIMEOUT env 로 요청 timeout 조정 (default 600 — free-form 생성이라 길 수 있고,
# 느린 HW(DGX Spark 등)에서 기본 60초로는 타임아웃 빈발. kreta KRETA_TIMEOUT 과 일관).
# 재실행 시 koffvqa_run.py 가 idempotent resume → 에러/타임아웃 항목만 재시도.
"$PY" "$SCRIPT_DIR/benches/koffvqa_run.py" \
  --model "$MODEL" \
  --base-url "$BASE_URL" \
  --timeout "${KOFFVQA_TIMEOUT:-600}"
PRED_XLSX=$(ls -t "$DEST"/*_gen.xlsx 2>/dev/null | head -1)
if [ -z "$PRED_XLSX" ]; then
  echo "[koffvqa] ERROR: 응답 xlsx 미생성"
  exit 1
fi
echo "[koffvqa] 응답 xlsx: $PRED_XLSX"

# 2) judge 단계
if [ "${LOCAL_JUDGE:-0}" = "1" ]; then
  # 로컬 KOFFVQA evaluate.py 사용
  JUDGE_MODEL="${JUDGE_MODEL:-google/gemma-2-9b-it}"
  echo "[koffvqa] === 로컬 judge ($JUDGE_MODEL) ==="
  cd "$BASE_DIR/data/KOFFVQA"
  "$PY" evaluate.py --predfile "$PRED_XLSX" --judge "$JUDGE_MODEL" || {
    echo "[koffvqa] ERROR: 로컬 evaluate.py 실패"
    exit 1
  }
elif [ "${API_JUDGE:-0}" = "1" ]; then
  if [ -z "$JUDGE_BASE_URL" ] || [ -z "$JUDGE_MODEL" ]; then
    echo "[koffvqa] ERROR: API_JUDGE=1 인데 JUDGE_MODEL/JUDGE_BASE_URL 미설정"
    exit 1
  fi
  echo "[koffvqa] === API judge ($JUDGE_MODEL @ $JUDGE_BASE_URL) ==="
  cd "$SCRIPT_DIR/benches"
  JUDGE_KEY_ARG=""
  if [ -n "$JUDGE_API_KEY" ]; then JUDGE_KEY_ARG="--judge-api-key $JUDGE_API_KEY"; fi
  "$PY" koffvqa_api_judge.py \
    --predfile "$PRED_XLSX" \
    --target-model "$MODEL" \
    --judge-model "$JUDGE_MODEL" \
    --judge-base-url "$JUDGE_BASE_URL" \
    $JUDGE_KEY_ARG || {
    echo "[koffvqa] ERROR: API judge 실패"
    exit 1
  }
else
  echo "[koffvqa] judge 단계 SKIP (LOCAL_JUDGE 또는 API_JUDGE env 미설정)"
  echo "  → 채점 별도 실행: cd $BASE_DIR/data/KOFFVQA && python evaluate.py --predfile $PRED_XLSX"
fi

echo "[koffvqa] done"
