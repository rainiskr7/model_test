#!/bin/bash
# vsm/multimodal 의존성 설치 + 외부 저장소 clone
#
# 외부 repo 들은 모두 <BASE>/data/ 에 중앙 집중 clone:
#   - data/KRETA          : 다양한 한국어 텍스트-리치 VQA (15영역 × 26유형)
#   - data/KOFFVQA        : Rubric 채점 한국어 free-form VQA
#   - data/KO-VLM-Benchmark : KO-VQA/KO-VDC/KO-OCRAG
#
# K-DTCBench, K-MMBench, MTVQA(KR) 는 HuggingFace datasets 라이브러리로 자동 다운로드.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA_DIR="$BASE_DIR/data"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# === 재현성: commit SHA 핀 (env var 로 override 가능) ===
# default 값은 2026-05-25 기준 Qwen3.6/Gemma 평가에서 실제 사용된 SHA.
# 다른 버전으로 평가하려면: KRETA_SHA=<sha> bash install.sh
KRETA_SHA="${KRETA_SHA:-c273302ade2c330f7afb7794cbbdd1ab0a3e0106}"
KOFFVQA_SHA="${KOFFVQA_SHA:-c6a861dd358d8220c802d52dfd0acf1a58a1f39b}"
KOVLM_SHA="${KOVLM_SHA:-d04d1f219478d676cb2faa9cb8e8fa34be917eb3}"

pin_repo() {
  local DIR="$1"
  local SHA="$2"
  if [ -n "$SHA" ]; then
    echo "[install] pin $DIR @ $SHA"
    ( cd "$DIR" && git checkout "$SHA" )
  else
    local CURRENT
    CURRENT=$( cd "$DIR" && git rev-parse HEAD 2>/dev/null )
    echo "[install] $DIR @ $CURRENT (latest, 핀 안 함)"
  fi
}

# 1) 커스텀 runner Python 의존성
"$BASE_DIR/.venv/bin/pip" install --quiet openai datasets pillow huggingface_hub pandas openpyxl

# 2) KRETA → data/KRETA
patch_kreta_infer_gpt() {
  # upstream infer_gpt.py 에 로컬 수정 일괄 적용 (patches/kreta_infer_gpt.patch):
  #   - BASE_URL / KRETA_WORKERS(default 2) env 지원
  #   - request timeout 60→300 (저대역폭 GB10 의 큰 비전 prefill 수용)
  #   - OpenAI 클라이언트 sample마다 생성→단일 재사용 (커넥션 누수 수정, 점진적 열화 방지)
  # pin_repo(git checkout SHA) 직후라 파일이 upstream 원본 → 항상 깨끗한 베이스에 apply.
  # (과거엔 sed 2줄로 BASE_URL/WORKERS 만 패치했으나, client 재사용은 다중라인 구조변경이라 patch 로 전환.)
  local PATCH="$SCRIPT_DIR/patches/kreta_infer_gpt.patch"
  if [ -f "$PATCH" ]; then
    ( cd KRETA && git checkout -- eval/infer/infer_gpt.py 2>/dev/null; git apply "$PATCH" ) \
      && echo "[install] KRETA infer_gpt.py 패치 적용 완료 (env/timeout/client 재사용)" \
      || echo "[install] WARN: KRETA infer_gpt.py 패치 실패 (이미 적용됐거나 SHA 불일치)"
  else
    echo "[install] WARN: $PATCH 없음 — KRETA infer_gpt.py 패치 스킵"
  fi
}

if [ ! -d "KRETA" ]; then
  git clone https://github.com/tabtoyou/KRETA.git
  pin_repo KRETA "$KRETA_SHA"
  ( cd KRETA && "$BASE_DIR/.venv/bin/pip" install -r requirements.txt )
  patch_kreta_infer_gpt
else
  echo "[install] data/KRETA 이미 존재"
  pin_repo KRETA "$KRETA_SHA"
  patch_kreta_infer_gpt
fi

# 3) KOFFVQA → data/KOFFVQA
if [ ! -d "KOFFVQA" ]; then
  git clone https://github.com/maum-ai/KOFFVQA.git
  pin_repo KOFFVQA "$KOFFVQA_SHA"
  ( cd KOFFVQA && "$BASE_DIR/.venv/bin/pip" install -r requirements.txt )
else
  echo "[install] data/KOFFVQA 이미 존재"
  pin_repo KOFFVQA "$KOFFVQA_SHA"
fi

# 4) KO-VLM-Benchmark → data/KO-VLM-Benchmark
if [ ! -d "KO-VLM-Benchmark" ]; then
  git clone https://github.com/Marker-Inc-Korea/KO-VLM-Benchmark.git
  pin_repo KO-VLM-Benchmark "$KOVLM_SHA"
  if [ -f "KO-VLM-Benchmark/requirements.txt" ]; then
    ( cd KO-VLM-Benchmark && "$BASE_DIR/.venv/bin/pip" install -r requirements.txt )
  fi
else
  echo "[install] data/KO-VLM-Benchmark 이미 존재"
  pin_repo KO-VLM-Benchmark "$KOVLM_SHA"
fi

echo "[install] done"
echo ""
echo "[install] === 재현성 가이드 ==="
echo "  최초 평가 후 안정성 확인되면 다음 SHA 들을 환경변수로 고정 권장:"
for D in KRETA KOFFVQA KO-VLM-Benchmark; do
  if [ -d "$D" ]; then
    echo "    $D: $(cd $D && git rev-parse HEAD)"
  fi
done
