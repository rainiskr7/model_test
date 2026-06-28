#!/bin/bash

# RESUME 전용 — run_kreta.sh 의 사본이되, ./output 의 jsonl 을 삭제하지 않음.
# 목적: 중단된 KRETA inference 를 처리된 id skip 으로 이어서 진행.
# 차이점: 원본 line 65 의 'find ./output ... *.jsonl ... -delete' 제거,
#         results.json 만 정리(stale 평가 방지). 그 외 로직 동일.
# Usage:
#   ./run_kreta_resume.sh [MODEL] [SETTING] [BASE_URL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

MODEL="${1:-qwen3-vl-8b-instruct}"
SETTING="${2:-default}"
BASE_URL="${3:-http://172.16.1.81:18090/v1}"

# safe_model_name: replace '/', '-', ':' with '_'
SAFE_MODEL="${MODEL//\//_}"
SAFE_MODEL="${SAFE_MODEL//-/_}"
SAFE_MODEL="${SAFE_MODEL//:/_}"

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
DEST="$BASE_DIR/results/$SAFE_MODEL/$TIMESTAMP/vision/multimodal/kreta"
mkdir -p "$DEST"

echo "[multimodal/kreta] BASE=$BASE_DIR"
echo "[multimodal/kreta] DEST=$DEST"

# KRETA repo 위치: <BASE>/data/KRETA (중앙 집중)
KRETA_REPO="$BASE_DIR/data/KRETA"

# 재현용 메타데이터 기록 (eval 실패해도 환경 정보 보존)
python "$SCRIPT_DIR/benches/common.py" \
  --out "$DEST/run_config.json" \
  --benchmark "KRETA" \
  --model "$MODEL" \
  --base-url "$BASE_URL" \
  --repo-dir "$KRETA_REPO" || echo "[kreta] run_config 작성 실패 (계속)"

# KRETA inference + evaluation
# infer_gpt.py 가 --base_url 인자 미지원이므로 env var 로 전달.
export OPENAI_BASE_URL="$BASE_URL"
# WORKERS env 로 동시성 조정 가능 (default 2 — GB10 메모리/대역폭 고려해 낮춤)
export KRETA_WORKERS="${KRETA_WORKERS:-2}"
# [thinking] 생성 상한/타임아웃은 공통 THINK_* 를 상속 (KRETA_* 로 개별 override 가능).
#   ⚠️ direct(1토큰 답) 모드는 thinking 과 비호환 — 추론을 못 쓰므로 default 사용 권장.
if [ "$SETTING" = "direct" ]; then
  echo "[multimodal/kreta] ⚠️ WARNING: 'direct' 모드는 thinking 파이프라인과 비호환입니다"
  echo "  (1토큰 답 강제 → 추론 불가). 'default' 모드를 쓰세요. 그래도 진행은 합니다."
fi
export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-${THINK_MAX_TOKENS:-8192}}"
export KRETA_TIMEOUT="${KRETA_TIMEOUT:-${THINK_TIMEOUT:-600}}"

cd "$KRETA_REPO/eval" || { echo "ERROR: $KRETA_REPO/eval not found. Run install.sh first."; exit 1; }

# RESUME MODE: jsonl 은 보존(이어하기), results.json 만 정리(stale 평가 방지).
# (원본 run_kreta.sh 는 jsonl 까지 삭제 → 처음부터 재실행. 여기선 의도적으로 보존.)
mkdir -p ./output
find ./output -maxdepth 1 -type f \( -name 'results.json' -o -name '*.jsonl.tmp' \) -delete || { echo "[multimodal/kreta] ERROR: ./output 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] RESUME: jsonl 보존, results.json 만 정리"

python infer/infer_gpt.py "$MODEL" "$SETTING" || { echo "[multimodal/kreta] ERROR: infer 실패(exit $?) — sample 누락/중단 의심, evaluate 스킵 후 중단"; exit 1; }
python evaluate.py || { echo "[multimodal/kreta] ERROR: evaluate 실패 — 중단"; exit 1; }

# KRETA 산출물 경로:
#   infer_gpt.py: ./output/{MODEL}_{part_name}.jsonl
#   evaluate.py:  ./output/results.json
if [ -d "./output" ]; then
  echo "[multimodal/kreta] copy ./output -> $DEST/"
  cp -r ./output/. "$DEST/" || { echo "[multimodal/kreta] ERROR: 결과 복사 실패 — 중단"; exit 1; }
else
  echo "[multimodal/kreta] WARN: ./output 디렉토리 없음 (KRETA 실행 실패 의심)"
  exit 1
fi

# 평가 후 검증: results.json 의 key 가 정확히 {MODEL}_{SETTING} 하나인지 assert.
# 정확 일치로 검사 → 빈 평가(0건)·stale jsonl 오염(다른 setting/모델)·중복키를 한 번에 차단.
python - <<PY || { echo "[multimodal/kreta] ERROR: results.json 검증 실패"; exit 1; }
import json, sys
from pathlib import Path
p = Path("$DEST/results.json")
if not p.exists():
    sys.exit(f"results.json 없음: {p}")
d = json.loads(p.read_text())
keys = list(d.keys())
expected = "$MODEL" + "_" + "$SETTING"
if keys != [expected]:
    sys.exit(f"results.json 키가 정확히 ['{expected}'] 가 아님: {keys} "
             f"(빈 평가/stale jsonl 오염/중복 의심)")
print(f"[multimodal/kreta] results.json keys OK: {keys}")
PY

echo "[multimodal/kreta] done"
