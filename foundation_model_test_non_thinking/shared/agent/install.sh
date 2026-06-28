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

# === 재현성: commit SHA 핀 (env var 로 override 가능) ===
# default 는 2026-05-25 기준 실제 평가 사용 SHA.
KO_AGENTBENCH_SHA="${KO_AGENTBENCH_SHA:-1174fedd9fa1c7177baa0cbff039a765c9b14d02}"

if [ ! -d "Ko-AgentBench" ]; then
  git clone https://github.com/Hugging-Face-KREW/Ko-AgentBench.git
fi
( cd Ko-AgentBench && git checkout "$KO_AGENTBENCH_SHA" )
echo "[agent/install] pin Ko-AgentBench @ $KO_AGENTBENCH_SHA"

# pyproject.toml 기반 설치
"$BASE_DIR/.venv/bin/pip" install -e "$DATA_DIR/Ko-AgentBench"

echo "[agent/install] done"
