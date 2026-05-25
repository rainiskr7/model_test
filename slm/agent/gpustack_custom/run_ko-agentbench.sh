#!/bin/bash
# Ko-AgentBench 실행 (run_gpustack_custom.sh 가 이 파일을 data/Ko-AgentBench/ 로 cp 후 호출)
#
# Usage:
#   bash run_ko-agentbench.sh MODEL [BASE_URL] [LEVELS]
#
# Defaults:
#   MODEL    = qwen3-vl-8b-instruct
#   BASE_URL = http://172.16.1.81:18090/v1/chat/completions
#   LEVELS   = "" (전체 L1~L7), "L1,L2" 식으로 일부만 가능

set -e

MODEL="${1:-qwen3-vl-8b-instruct}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
LEVELS="${3:-}"

# venv python 경로 결정: MODEL_TEST_BASE env 우선, 없으면 추정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

ARGS=(--model "$MODEL" --base_url "$BASE_URL")
if [ -n "$LEVELS" ]; then
  ARGS+=(--levels "$LEVELS")
fi

"$PY" run_gpustack_benchmark_with_logging.py "${ARGS[@]}"
