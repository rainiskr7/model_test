#!/bin/bash
# GPUStack 어댑터 + runner 를 Ko-AgentBench (data/Ko-AgentBench) 안으로 복사 후 실행
#
# Ko-AgentBench repo 위치: <BASE>/data/Ko-AgentBench
#
# Usage:
#   ./run_gpustack_custom.sh MODEL [BASE_URL] [LEVELS]
#
# AGENT_TRACK_NAME 으로 결과/채점 트랙을 분리한다 (기본 agent).
#   AGENT_TRACK_NAME=agent_smoke ./run_gpustack_custom.sh MODEL ...
# 러너·채점기에 같은 값이 전달되므로 둘이 어긋나지 않는다. 변형 트랙 결과는
# canonical agent 트랙과 섞지 말 것 (CONVENTIONS.md §4).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# vsm/agent/<this> → vsm/agent → vsm → model_test
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# adapter 는 Ko-AgentBench 로 복사되어 실행되므로 __file__ 로는 shared/ 를 못 찾는다.
# MODEL_TEST_BASE 를 export 해 두어야 standalone 실행에서도 서빙 제약이 적용된다.
export MODEL_TEST_BASE="$BASE_DIR"
KOA_DIR="$BASE_DIR/data/Ko-AgentBench"

MODEL="${1:?MODEL required: ./run_gpustack_custom.sh MODEL [BASE_URL] [LEVELS]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
LEVELS="${3:-}"
SCORING_TRACK="${AGENT_TRACK_NAME:-agent}"

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

# 실행
cd "$KOA_DIR"
bash run_ko-agentbench.sh "$MODEL" "$BASE_URL" "$LEVELS" "$SCORING_TRACK"

SCORING_TS="${EVAL_TIMESTAMP:-}"
if [ -z "$SCORING_TS" ] && [ -f "$BASE_DIR/.eval_session" ]; then
  SCORING_TS="$(cat "$BASE_DIR/.eval_session")"
fi
PY="${PY:-$BASE_DIR/.venv/bin/python}"

if "$PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$SCORING_TS" \
  --track "$SCORING_TRACK"; then
  :
else
  SCORING_RC=$?
  SCORING_SAFE_MODEL="${MODEL//\//_}"
  SCORING_SAFE_MODEL="${SCORING_SAFE_MODEL//-/_}"
  SCORING_SAFE_MODEL="${SCORING_SAFE_MODEL//:/_}"
  SCORING_RESULTS_DIR="$BASE_DIR/results/$SCORING_SAFE_MODEL/$SCORING_TS/language/$SCORING_TRACK"
  echo "[agent-scoring] 평가 결과(L*.json)는 ${SCORING_RESULTS_DIR}에 그대로 보존되어 있지만 채점에 실패하여 summary.json이 작성되지 않았습니다. 채점만 다시 실행하세요." >&2
  exit "$SCORING_RC"
fi
