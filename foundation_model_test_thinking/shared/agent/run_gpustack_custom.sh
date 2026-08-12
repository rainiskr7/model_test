#!/bin/bash
# GPUStack 어댑터 + runner 를 Ko-AgentBench (data/Ko-AgentBench) 안으로 복사 후 실행
#
# Ko-AgentBench repo 위치: <BASE>/data/Ko-AgentBench
#
# Usage:
#   ./run_gpustack_custom.sh MODEL [BASE_URL] [LEVELS]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# vsm/agent/<this> → vsm/agent → vsm → model_test
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
KOA_DIR="$BASE_DIR/data/Ko-AgentBench"

MODEL="${1:?MODEL required: ./run_gpustack_custom.sh MODEL [BASE_URL] [LEVELS]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
LEVELS="${3:-}"

if [ ! -d "$KOA_DIR" ]; then
  echo "ERROR: $KOA_DIR 없음. 먼저 install.sh 실행."
  exit 1
fi

# 커스텀 파일 복사
cp "$SCRIPT_DIR/gpustack_custom/run_gpustack_benchmark_with_logging.py" \
   "$KOA_DIR/run_gpustack_benchmark_with_logging.py"
cp "$SCRIPT_DIR/gpustack_custom/run_ko-agentbench.sh" \
   "$KOA_DIR/run_ko-agentbench.sh"
cp "$SCRIPT_DIR/gpustack_custom/openai_compat_adapter.py" \
   "$KOA_DIR/bench/adapters/openai_compat_adapter.py"
cp "$SCRIPT_DIR/gpustack_custom/tool_call_parser.py" \
   "$KOA_DIR/bench/adapters/tool_call_parser.py"
# adapter 가 import 하는 reasoning 모듈도 함께 복사 (thinking 추론 분리 — 없으면 ModuleNotFoundError)
cp "$SCRIPT_DIR/gpustack_custom/reasoning.py" \
   "$KOA_DIR/bench/adapters/reasoning.py"

# 실행
cd "$KOA_DIR"
bash run_ko-agentbench.sh "$MODEL" "$BASE_URL" "$LEVELS"

SCORING_TS="${EVAL_TIMESTAMP:-}"
if [ -z "$SCORING_TS" ] && [ -f "$BASE_DIR/.eval_session" ]; then
  SCORING_TS="$(cat "$BASE_DIR/.eval_session")"
fi
SCORING_TRACK="${AGENT_TRACK_NAME:-agent}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

"$PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$SCORING_TS" \
  --track "$SCORING_TRACK" \
  || echo "[agent-scoring] 실패 — 계속"
