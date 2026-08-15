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
# 결과 저장 subfolder. 채점 훅이 보는 경로(run_gpustack_custom.sh 의 AGENT_TRACK_NAME)와
# 같은 값을 써야 한다 — 안 넘기면 러너는 항상 default 'agent' 에 쓴다.
if [ -n "${AGENT_TRACK_NAME:-}" ]; then
  ARGS+=(--track-name "$AGENT_TRACK_NAME")
fi

"$PY" run_gpustack_benchmark_with_logging.py "${ARGS[@]}"
