#!/bin/bash
# Ko-AgentBench 실행 (run_gpustack_custom.sh 가 이 파일을 data/Ko-AgentBench/ 로 cp 후 호출)
#
# Usage:
#   bash run_ko-agentbench.sh MODEL [BASE_URL] [LEVELS] [TRACK_NAME] [REQUEST_TIMEOUT] [TASK_TIMEOUT] [MAX_RETRIES]
#
# Defaults:
#   MODEL    = qwen3-vl-8b-instruct
#   BASE_URL = http://172.16.1.81:18090/v1/chat/completions
#   LEVELS   = "" (전체 L1~L7), "L1,L2" 식으로 일부만 가능
#   TRACK_NAME = agent
#   REQUEST_TIMEOUT = unset (runner default; one HTTP chat-completion request)
#   TASK_TIMEOUT = unset (runner default; one whole task across all steps)
#   MAX_RETRIES = unset (runner default: 2 harness attempts)

set -e

MODEL="${1:-qwen3-vl-8b-instruct}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
LEVELS="${3:-}"
TRACK_NAME="${4:-agent}"
REQUEST_TIMEOUT="${5:-}"
TASK_TIMEOUT="${6:-}"
MAX_RETRIES="${7:-}"

# venv python 경로 결정: MODEL_TEST_BASE env 우선, 없으면 추정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

ARGS=(--model "$MODEL" --base_url "$BASE_URL" --track-name "$TRACK_NAME")
if [ -n "$LEVELS" ]; then
  ARGS+=(--levels "$LEVELS")
fi
if [ -n "$REQUEST_TIMEOUT" ]; then
  ARGS+=(--request-timeout "$REQUEST_TIMEOUT")
fi
if [ -n "$TASK_TIMEOUT" ]; then
  ARGS+=(--timeout "$TASK_TIMEOUT")
fi
if [ -n "$MAX_RETRIES" ]; then
  ARGS+=(--max-retries "$MAX_RETRIES")
fi

"$PY" run_gpustack_benchmark_with_logging.py "${ARGS[@]}"
