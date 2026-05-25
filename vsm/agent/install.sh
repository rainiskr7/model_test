#!/bin/bash
# Ko-AgentBench 설치
# https://github.com/Hugging-Face-KREW/Ko-AgentBench
#
# clone 위치: <BASE>/data/Ko-AgentBench (중앙 집중)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA_DIR="$BASE_DIR/data"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

if [ ! -d "Ko-AgentBench" ]; then
  git clone --depth 1 https://github.com/Hugging-Face-KREW/Ko-AgentBench.git
fi

# pyproject.toml 기반 설치
"$BASE_DIR/.venv/bin/pip" install -e "$DATA_DIR/Ko-AgentBench"

echo "[agent/install] done"
