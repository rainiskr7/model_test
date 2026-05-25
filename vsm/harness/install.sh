#!/bin/bash
# LM-Evaluation-Harness 설치
# https://github.com/EleutherAI/lm-evaluation-harness
#
# clone 위치: <BASE>/data/lm-evaluation-harness (중앙 집중)
# 평가 시점: 시스템에 lm_eval 명령이 설치되어 있으면 어느 클래스 폴더에서나 호출 가능.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA_DIR="$BASE_DIR/data"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

if [ ! -d "lm-evaluation-harness" ]; then
  git clone --depth 1 https://github.com/EleutherAI/lm-evaluation-harness.git
fi

"$BASE_DIR/.venv/bin/pip" install -e "$DATA_DIR/lm-evaluation-harness"
"$BASE_DIR/.venv/bin/pip" install "lm_eval[api]"

echo "[harness/install] done. lm_eval 명령 사용 가능."
