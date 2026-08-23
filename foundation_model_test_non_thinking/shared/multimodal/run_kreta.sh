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
PUBLISH_CLI="$BASE_DIR/derive_multimodal_publish.py"

# 실제 요청값을 provenance에도 동일하게 기록한다.
if [ "$SETTING" = "direct" ]; then
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-32}"
else
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-4096}"
fi

# 재현용 메타데이터 기록 (eval 실패해도 환경 정보 보존)
python "$SCRIPT_DIR/benches/common.py" \
  --out "$DEST/run_config.json" \
  --benchmark "KRETA" \
  --model "$MODEL" \
  --base-url "$BASE_URL" \
  --max-tokens "$KRETA_MAX_TOKENS" \
  --repo-dir "$KRETA_REPO" || { echo "[kreta] run_config 작성 실패 — 중단"; exit 1; }

# KRETA inference + evaluation
# infer_gpt.py 가 --base_url 인자 미지원이므로 env var 로 전달.
# (KRETA install 후 BASE_URL 라인을 os.environ.get(...) 으로 패치된 상태)
export OPENAI_BASE_URL="$BASE_URL"
# WORKERS env 로 동시성 조정 가능 (default 2 — GB10 메모리 압박으로 4는 모델 인스턴스 hang 유발 사례 있어 낮춤)
export KRETA_WORKERS="${KRETA_WORKERS:-2}"
cd "$KRETA_REPO/eval" || { echo "ERROR: $KRETA_REPO/eval not found. Run install.sh first."; exit 1; }

# KRETA evaluate.py 는 ./output 안의 모든 jsonl 을 일괄 평가해 results.json 에 누적함.
# 이전 모델의 jsonl 이 남아 있으면 cross-contamination 발생 → 평가 전 cleanup.
mkdir -p ./output
find ./output -maxdepth 1 -type f \( -name '*.jsonl' -o -name '*.jsonl.tmp' -o -name 'results.json' -o -name '.resume_context.json' \) -delete || { echo "[multimodal/kreta] ERROR: ./output 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] ./output stale 정리 완료"

# resume은 이 정확한 실행 문맥에서 생성된 checkpoint만 이어받을 수 있다.
python - "./output/.resume_context.json" "$MODEL" "$SETTING" "$BASE_URL" "$TIMESTAMP" "$KRETA_MAX_TOKENS" <<'PY' || exit 1
import json, os, sys
from pathlib import Path

path = Path(sys.argv[1])
value = {
    "model": sys.argv[2], "setting": sys.argv[3], "base_url": sys.argv[4],
    "session": sys.argv[5], "max_tokens": int(sys.argv[6]),
}
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
os.replace(tmp, path)
PY

INFER_RC=0
python infer/infer_gpt.py "$MODEL" "$SETTING" || INFER_RC=$?
CHECKPOINT="./output/${MODEL}_${SETTING}.jsonl"
if [ ! -f "$CHECKPOINT" ]; then
  echo "[multimodal/kreta] ERROR: checkpoint 없음: $CHECKPOINT"
  exit 1
fi
DEST_JSONL="$DEST/$(basename "$CHECKPOINT")"
cp "$CHECKPOINT" "$DEST_JSONL" || { echo "[multimodal/kreta] ERROR: checkpoint 보존 실패"; exit 1; }

# evaluate.py 전에 raw 타입/완주/id preflight. 실패 sidecar를 쓴 뒤 점수 계산을 막는다.
if ! python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" --preflight-kreta --write; then
  echo "[multimodal/kreta] ERROR: raw preflight 실패 — checkpoint 보존, evaluate 스킵"
  exit 1
fi
if [ "$INFER_RC" -ne 0 ]; then
  python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" \
    --reject-reason "infer 실패(exit $INFER_RC)" --write || true
  echo "[multimodal/kreta] ERROR: infer 실패(exit $INFER_RC) — evaluate 스킵"
  exit 1
fi

python evaluate.py || {
  python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" \
    --reject-reason "evaluate.py 실패" --write || true
  echo "[multimodal/kreta] ERROR: evaluate 실패 — REJECTED sidecar 기록 후 중단"
  exit 1
}

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

# raw 재집계와 results.json 일치까지 통과한 경우에만 NATIVE 승격한다.
python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" --native --write || {
  echo "[multimodal/kreta] ERROR: post-evaluate 검증 실패 — REJECTED sidecar 기록됨"
  exit 1
}

echo "[multimodal/kreta] done"
