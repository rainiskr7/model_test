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

SAFE_MODEL="$(python - "$SCRIPT_DIR/benches" "$BASE_DIR" "$MODEL" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from paths import results_model_dir_name
print(results_model_dir_name(sys.argv[2], sys.argv[3]))
PY
)" || { echo "[kreta] results 모델 경로 해석 실패 — 중단"; exit 1; }

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
export OPENAI_BASE_URL="$BASE_URL"
# WORKERS env 로 동시성 조정 가능 (default 2 — GB10 메모리/대역폭 고려해 낮춤)
export KRETA_WORKERS="${KRETA_WORKERS:-2}"
cd "$KRETA_REPO/eval" || { echo "ERROR: $KRETA_REPO/eval not found. Run install.sh first."; exit 1; }

# RESUME MODE: jsonl 은 보존(이어하기), results.json 만 정리(stale 평가 방지).
# (원본 run_kreta.sh 는 jsonl 까지 삭제 → 처음부터 재실행. 여기선 의도적으로 보존.)
mkdir -p ./output
CHECKPOINT="./output/${MODEL}_${SETTING}.jsonl"
# Fresh run이 results/에 보존한 checkpoint/context를 중앙 output이 지워진
# 경우에도 같은 세션에 한해 복구한다.
if [ ! -f "$CHECKPOINT" ] && [ -f "$DEST/$(basename "$CHECKPOINT")" ]; then
  cp "$DEST/$(basename "$CHECKPOINT")" "$CHECKPOINT" || exit 1
  echo "[multimodal/kreta] results/ 보존본에서 checkpoint 복구"
fi
if [ ! -f "./output/.resume_context.json" ] && [ -f "$DEST/.resume_context.json" ]; then
  cp "$DEST/.resume_context.json" "./output/.resume_context.json" || exit 1
  echo "[multimodal/kreta] results/ 보존본에서 resume context 복구"
fi
if [ ! -f "$CHECKPOINT" ] || [ ! -f "./output/.resume_context.json" ]; then
  echo "[multimodal/kreta] ERROR: 검증 가능한 checkpoint/context 없음 — 새 run_kreta.sh 실행 필요"
  exit 1
fi
if ! python - "$SCRIPT_DIR/benches" "$DEST/run_config.json" "./output/.resume_context.json" "$SETTING" "$TIMESTAMP" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from metadata import build_resume_context

config = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
path = Path(sys.argv[3])
expected = build_resume_context(config, setting=sys.argv[4], session=sys.argv[5])
try:
    actual = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"resume context 읽기 실패: {exc}")
if actual != expected:
    raise SystemExit(f"stale resume context 거부: expected={expected!r}, actual={actual!r}")
PY
then
  echo "[multimodal/kreta] ERROR: 현재 실행 문맥과 checkpoint가 다름 — resume 중단"
  exit 1
fi
# evaluate.py가 다른 모델 jsonl까지 일괄 읽지 못하도록 현재 checkpoint 외에는 제거한다.
find ./output -maxdepth 1 -type f -name '*.jsonl' ! -name "$(basename "$CHECKPOINT")" -delete || { echo "[multimodal/kreta] ERROR: foreign checkpoint 정리 실패"; exit 1; }
find ./output -maxdepth 1 -type f \( -name 'results.json' -o -name '*.jsonl.tmp' \) -delete || { echo "[multimodal/kreta] ERROR: ./output 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] RESUME: 문맥 일치 checkpoint만 보존"

INFER_RC=0
python infer/infer_gpt.py "$MODEL" "$SETTING" || INFER_RC=$?
if [ ! -f "$CHECKPOINT" ]; then
  echo "[multimodal/kreta] ERROR: checkpoint 없음: $CHECKPOINT"
  exit 1
fi
DEST_JSONL="$DEST/$(basename "$CHECKPOINT")"
cp "$CHECKPOINT" "$DEST_JSONL" || { echo "[multimodal/kreta] ERROR: checkpoint 보존 실패"; exit 1; }
cp "./output/.resume_context.json" "$DEST/.resume_context.json" || { echo "[multimodal/kreta] ERROR: resume context 보존 실패"; exit 1; }

if ! python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" --preflight-kreta --write; then
  echo "[multimodal/kreta] ERROR: raw preflight 실패 — checkpoint 보존, evaluate 스킵"
  echo "[multimodal/kreta] 복구 ① 일시 오류: 동일 환경·동일 세션으로 run_kreta_resume.sh"
  echo "[multimodal/kreta] 복구 ② 반복 diffusion None: 새 세션에서 SERVING_FORCE_SKIP_SPECIAL_TOKENS=false run_kreta.sh"
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
