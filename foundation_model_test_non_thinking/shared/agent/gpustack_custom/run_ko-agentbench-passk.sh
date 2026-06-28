#!/bin/bash
# Ko-AgentBench pass@k 보조 트랙 (Ko-AgentBench/ 디렉토리 안에서 실행됨)
#
# temperature 0.3~0.7 + repetitions N 으로 분산 측정.
# 결과 저장 위치: results/<safe_model>/<timestamp>/language/agent_passk/L1.json ...
#
# Usage (run_gpustack_passk.sh 가 호출):
#   bash run_ko-agentbench-passk.sh MODEL [BASE_URL] [TEMP] [REPS]

MODEL="${1:?MODEL required}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
TEMP="${3:-0.7}"
REPS="${4:-5}"

# venv python 경로 결정: MODEL_TEST_BASE env 우선, 없으면 추정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

"$PY" run_gpustack_benchmark_with_logging.py \
  --model "$MODEL" \
  --base_url "$BASE_URL" \
  --temperature "$TEMP" \
  --repetitions "$REPS" \
  --track-name agent_passk
