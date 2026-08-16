#!/bin/bash
# Ko-AgentBench pass@k 보조 트랙 외부 wrapper
#
# 메인 트랙 (run_gpustack_custom.sh) 과 동일 파이프라인이지만:
#   - temperature 0.3~0.7 (default 0.7)
#   - --repetitions N (default 5)
#   - --track-name agent_passk → 결과가 language/agent_passk/ 로 분리 저장
#
# Ko-AgentBench repo 위치: <BASE>/data/Ko-AgentBench
#
# Usage:
#   ./run_gpustack_passk.sh MODEL [BASE_URL] [TEMP] [REPS]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# vsm/agent/<this> → vsm/agent → vsm → model_test
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
KOA_DIR="$BASE_DIR/data/Ko-AgentBench"

MODEL="${1:?MODEL required: ./run_gpustack_passk.sh MODEL [BASE_URL] [TEMP] [REPS]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
TEMP="${3:-0.7}"
REPS="${4:-5}"

if [ ! -d "$KOA_DIR" ]; then
  echo "ERROR: $KOA_DIR 없음. 먼저 install.sh 실행."
  exit 1
fi

# 메인 파일이 Ko-AgentBench 내부에 있는지 확인 + 갱신 복사
cp -u "$SCRIPT_DIR/gpustack_custom/run_gpustack_benchmark_with_logging.py" \
      "$KOA_DIR/run_gpustack_benchmark_with_logging.py"
cp -u "$SCRIPT_DIR/gpustack_custom/openai_compat_adapter.py" \
      "$KOA_DIR/bench/adapters/openai_compat_adapter.py"
cp "$SCRIPT_DIR/gpustack_custom/tool_call_parser.py" \
   "$KOA_DIR/bench/adapters/tool_call_parser.py"
# adapter 가 import 하는 reasoning 모듈도 함께 복사 (없으면 ModuleNotFoundError)
cp -u "$SCRIPT_DIR/gpustack_custom/reasoning.py" \
      "$KOA_DIR/bench/adapters/reasoning.py"
cp "$SCRIPT_DIR/gpustack_custom/run_ko-agentbench-passk.sh" \
   "$KOA_DIR/run_ko-agentbench-passk.sh"

cd "$KOA_DIR"
bash run_ko-agentbench-passk.sh "$MODEL" "$BASE_URL" "$TEMP" "$REPS"
