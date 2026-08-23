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
PUBLISH_CLI="$BASE_DIR/derive_multimodal_publish.py"

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
# 모드별 생성 상한 기본값 (env 로 override 가능):
#   direct(글자만 답) → 32 로 작게: 타임아웃·절단 없음, GB10 등 느린 HW 안전.
#   default(추론 후 답) → 4096: 추론 공간 확보(짧추면 긴 답 절단 → 답 유실).
if [ "$SETTING" = "direct" ]; then
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-32}"
else
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-4096}"
fi

cd "$KRETA_REPO/eval" || { echo "ERROR: $KRETA_REPO/eval not found. Run install.sh first."; exit 1; }

# RESUME MODE: jsonl 은 보존(이어하기), results.json 만 정리(stale 평가 방지).
# (원본 run_kreta.sh 는 jsonl 까지 삭제 → 처음부터 재실행. 여기선 의도적으로 보존.)
mkdir -p ./output
find ./output -maxdepth 1 -type f \( -name 'results.json' -o -name '*.jsonl.tmp' \) -delete || { echo "[multimodal/kreta] ERROR: ./output 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] RESUME: jsonl 보존, results.json 만 정리"

INFER_RC=0
python infer/infer_gpt.py "$MODEL" "$SETTING" || INFER_RC=$?
CHECKPOINT="./output/${MODEL}_${SETTING}.jsonl"
if [ ! -f "$CHECKPOINT" ]; then
  echo "[multimodal/kreta] ERROR: checkpoint 없음: $CHECKPOINT"
  exit 1
fi
DEST_JSONL="$DEST/$(basename "$CHECKPOINT")"
cp "$CHECKPOINT" "$DEST_JSONL" || { echo "[multimodal/kreta] ERROR: checkpoint 보존 실패"; exit 1; }

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

python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" --native --write || {
  echo "[multimodal/kreta] ERROR: post-evaluate 검증 실패 — REJECTED sidecar 기록됨"
  exit 1
}

echo "[multimodal/kreta] done"
