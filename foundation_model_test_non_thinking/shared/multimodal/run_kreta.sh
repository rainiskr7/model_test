#!/bin/bash

# Usage:
#   ./run_kreta.sh [MODEL] [SETTING] [BASE_URL]
# Defaults:
#   MODEL    = qwen3-vl-8b-instruct
#   SETTING  = default
#   BASE_URL = http://172.16.1.81:18090/v1
#
# 결과 경로: <MODEL_TEST_BASE>/results/<safe_model>/<timestamp>/vision/multimodal/kreta/
#   - MODEL_TEST_BASE env: 미설정 시 스크립트 위치 기준 ../.. 로 자동 추정
#   - EVAL_TIMESTAMP env: 미설정 시 현재 시각으로 자동 생성

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
# (KRETA install 후 BASE_URL 라인을 os.environ.get(...) 으로 패치된 상태)
export OPENAI_BASE_URL="$BASE_URL"
# WORKERS env 로 동시성 조정 가능 (default 2 — GB10 메모리 압박으로 4는 모델 인스턴스 hang 유발 사례 있어 낮춤)
export KRETA_WORKERS="${KRETA_WORKERS:-2}"
# 모드별 생성 상한 기본값 (env 로 override 가능):
#   direct(글자만 답) → 32 로 작게: 타임아웃·절단 없음, GB10 등 느린 HW 안전.
#   default(추론 후 답) → 4096: 추론 공간 확보(짧추면 긴 답 절단 → 답 유실).
if [ "$SETTING" = "direct" ]; then
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-32}"
else
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-4096}"
fi

cd "$KRETA_REPO/eval" || { echo "ERROR: $KRETA_REPO/eval not found. Run install.sh first."; exit 1; }

# KRETA evaluate.py 는 ./output 안의 모든 jsonl 을 일괄 평가해 results.json 에 누적함.
# 이전 모델의 jsonl 이 남아 있으면 cross-contamination 발생 → 평가 전 cleanup.
mkdir -p ./output
find ./output -maxdepth 1 -type f \( -name '*.jsonl' -o -name '*.jsonl.tmp' -o -name 'results.json' \) -delete || { echo "[multimodal/kreta] ERROR: ./output 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] ./output stale 정리 완료"

python infer/infer_gpt.py "$MODEL" "$SETTING" || { echo "[multimodal/kreta] ERROR: infer 실패(exit $?) — sample 누락/중단 의심, evaluate 스킵 후 중단"; exit 1; }
python evaluate.py || { echo "[multimodal/kreta] ERROR: evaluate 실패 — 중단"; exit 1; }

# KRETA 산출물 경로 (KRETA 소스 확인 결과):
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
