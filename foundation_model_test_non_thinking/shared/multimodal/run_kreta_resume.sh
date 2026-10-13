#!/bin/bash

# RESUME 전용 — run_kreta.sh 의 사본이되, 답안 폴더의 jsonl 을 삭제하지 않음.
# 목적: 중단된 KRETA inference 를 처리된 id skip 으로 이어서 진행.
# 차이점: 원본의 stale 정리(jsonl 삭제) 제거, results.json 만 정리(stale 평가 방지). 그 외 로직 동일.
# Usage:
#   ./run_kreta_resume.sh [MODEL] [SETTING] [BASE_URL]
# 답안(checkpoint) 폴더는 run_kreta.sh 와 같은 규칙: <KRETA_OUTPUT_ROOT>/<safe_model>/<timestamp>/<setting>/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/kreta_output_dir.sh"

MODEL="${1:-qwen3-vl-8b-instruct}"
SETTING="${2:-default}"
BASE_URL="${3:-http://172.16.1.81:18090/v1}"

kreta_reject_bad_model_name "$MODEL" || exit 1

# 경로 해석에 쓸 인터프리터를 먼저 정한다. bare `python` 은 이 저장소의
# 실행 환경(macOS·리눅스 모두)에 없을 수 있고, 없으면 DEST 를 만들기도 전에
# 스크립트가 죽는다.
PY="${PY:-}"
if [ -z "$PY" ]; then
  for candidate in "$BASE_DIR/.venv/bin/python" python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  done
fi
[ -n "$PY" ] || { echo "[kreta] python 인터프리터를 찾지 못함 — 중단"; exit 1; }

SAFE_MODEL="$("$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); from paths import results_model_dir_name; print(results_model_dir_name(sys.argv[2], sys.argv[3]))' "$SCRIPT_DIR/benches" "$BASE_DIR" "$MODEL")" || { echo "[kreta] results 모델 경로 해석 실패 — 중단"; exit 1; }

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

# KRETA repo 위치: <BASE>/data/KRETA (중앙 집중)
KRETA_REPO="$BASE_DIR/data/KRETA"
PUBLISH_CLI="$BASE_DIR/derive_multimodal_publish.py"
KRETA_OUTPUT_ROOT="${KRETA_OUTPUT_ROOT:-$KRETA_REPO/eval/output}"
OUT="$(kreta_output_dir "$KRETA_OUTPUT_ROOT" "$SAFE_MODEL" "$TIMESTAMP" "$SETTING")"
export KRETA_OUTPUT_DIR="$OUT"

echo "[multimodal/kreta] BASE=$BASE_DIR"
echo "[multimodal/kreta] DEST=$DEST"
echo "[multimodal/kreta] OUTPUT_DIR=$OUT"

if [ "$SETTING" = "direct" ]; then
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-32}"
else
  export KRETA_MAX_TOKENS="${KRETA_MAX_TOKENS:-4096}"
fi

# 이 답안 폴더의 유일한 writer 임을 먼저 확보한다.
kreta_acquire_writer_lock "$OUT" || exit 1

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
CHECKPOINT="$OUT/${MODEL}_${SETTING}.jsonl"
# Fresh run이 results/에 보존한 checkpoint/context를 답안 폴더가 잃은 경우에도
# 같은 세션에 한해 복구한다.
if [ ! -f "$CHECKPOINT" ] && [ -f "$DEST/$(basename "$CHECKPOINT")" ]; then
  cp "$DEST/$(basename "$CHECKPOINT")" "$CHECKPOINT" || exit 1
  echo "[multimodal/kreta] results/ 보존본에서 checkpoint 복구"
fi
if [ ! -f "$OUT/.resume_context.json" ] && [ -f "$DEST/.resume_context.json" ]; then
  cp "$DEST/.resume_context.json" "$OUT/.resume_context.json" || exit 1
  echo "[multimodal/kreta] results/ 보존본에서 resume context 복구"
fi
if [ ! -f "$CHECKPOINT" ] || [ ! -f "$OUT/.resume_context.json" ]; then
  echo "[multimodal/kreta] ERROR: 검증 가능한 checkpoint/context 없음 — 새 run_kreta.sh 실행 필요"
  exit 1
fi
if ! python "$SCRIPT_DIR/benches/kreta_resume_context_check.py" "$SCRIPT_DIR/benches" "$DEST/run_config.json" "$OUT/.resume_context.json" "$SETTING" "$TIMESTAMP"
then
  echo "[multimodal/kreta] ERROR: 현재 실행 문맥과 checkpoint가 다름 — resume 중단"
  exit 1
fi
# 답안 폴더는 실행마다 다르므로 다른 실행의 jsonl 이 있을 수 없지만, evaluate.py 가 폴더를
# 일괄 읽으므로 방어적으로 현재 checkpoint 외에는 제거한다.
find "$OUT" -maxdepth 1 -type f -name '*.jsonl' ! -name "$(basename "$CHECKPOINT")" -delete || { echo "[multimodal/kreta] ERROR: foreign checkpoint 정리 실패"; exit 1; }
find "$OUT" -maxdepth 1 -type f \( -name 'results.json' -o -name '*.jsonl.tmp' \) -delete || { echo "[multimodal/kreta] ERROR: 답안 폴더 정리 실패 — 중단"; exit 1; }
echo "[multimodal/kreta] RESUME: 문맥 일치 checkpoint만 보존"

INFER_RC=0
python infer/infer_gpt.py "$MODEL" "$SETTING" || INFER_RC=$?
if [ ! -f "$CHECKPOINT" ]; then
  echo "[multimodal/kreta] ERROR: checkpoint 없음: $CHECKPOINT"
  exit 1
fi
DEST_JSONL="$DEST/$(basename "$CHECKPOINT")"
cp "$CHECKPOINT" "$DEST_JSONL" || { echo "[multimodal/kreta] ERROR: checkpoint 보존 실패"; exit 1; }
cp "$OUT/.resume_context.json" "$DEST/.resume_context.json" || { echo "[multimodal/kreta] ERROR: resume context 보존 실패"; exit 1; }

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

# upstream evaluate.py 의 __main__ 은 ./output 고정이라 check_files(폴더) 를 직접 부른다.
python "$SCRIPT_DIR/benches/kreta_output_check.py" "$OUT" || {
  python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" \
    --reject-reason "evaluate.py 실패" --write || true
  echo "[multimodal/kreta] ERROR: evaluate 실패 — REJECTED sidecar 기록 후 중단"
  exit 1
}

echo "[multimodal/kreta] copy $OUT -> $DEST/"
kreta_copy_artifacts "$OUT" "$DEST" || { echo "[multimodal/kreta] ERROR: 결과 복사 실패 — 중단"; exit 1; }

python "$PUBLISH_CLI" --base "$BASE_DIR" --source "$DEST_JSONL" --native --write || {
  echo "[multimodal/kreta] ERROR: post-evaluate 검증 실패 — REJECTED sidecar 기록됨"
  exit 1
}

echo "[multimodal/kreta] done"
