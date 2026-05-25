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

# === 재현성: env var 로 commit SHA 핀 ===
KRETA_SHA="${KRETA_SHA:-}"
KOFFVQA_SHA="${KOFFVQA_SHA:-}"
KOVLM_SHA="${KOVLM_SHA:-}"

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
  local F="KRETA/eval/infer/infer_gpt.py"
  if [ -f "$F" ]; then
    # BASE_URL 을 env 변수로 받게
    sed -i 's|^BASE_URL = "https://api.openai.com/v1"$|BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")|' "$F"
    # WORKERS 를 env 변수로 받게 (default 4, 기존 hardcoded 20 → 서버 부하 완화)
    sed -i 's|^WORKERS = 20$|WORKERS = int(os.environ.get("KRETA_WORKERS", "4"))|' "$F"
    echo "[install] KRETA infer_gpt.py 패치 완료 (BASE_URL/WORKERS env 지원)"
  fi
}

if [ ! -d "KRETA" ]; then
  git clone --depth 1 https://github.com/tabtoyou/KRETA.git
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
  git clone --depth 1 https://github.com/maum-ai/KOFFVQA.git
  pin_repo KOFFVQA "$KOFFVQA_SHA"
  ( cd KOFFVQA && "$BASE_DIR/.venv/bin/pip" install -r requirements.txt )
else
  echo "[install] data/KOFFVQA 이미 존재"
  pin_repo KOFFVQA "$KOFFVQA_SHA"
fi

# 4) KO-VLM-Benchmark → data/KO-VLM-Benchmark
if [ ! -d "KO-VLM-Benchmark" ]; then
  git clone --depth 1 https://github.com/Marker-Inc-Korea/KO-VLM-Benchmark.git
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
