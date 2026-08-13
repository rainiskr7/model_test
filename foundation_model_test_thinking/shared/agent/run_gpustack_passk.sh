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
#   ./run_gpustack_passk.sh MODEL [BASE_URL] [TEMP] [REPS] [LEVELS]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# vsm/agent/<this> → vsm/agent → vsm → model_test
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# adapter/runner 는 Ko-AgentBench 로 복사되어 실행되므로 __file__ 로는 shared/ 를 못 찾는다.
# MODEL_TEST_BASE 를 export 해 두어야 standalone 실행에서도 결과 경로와 세션 파일이
# 올바르게 잡힌다.
export MODEL_TEST_BASE="$BASE_DIR"
KOA_DIR="$BASE_DIR/data/Ko-AgentBench"

MODEL="${1:?MODEL required: ./run_gpustack_passk.sh MODEL [BASE_URL] [TEMP] [REPS] [LEVELS]}"
BASE_URL="${2:-http://172.16.1.81:18090/v1/chat/completions}"
TEMP="${3:-0.7}"
REPS="${4:-5}"
# 전체 L1~L7 이 기본. "L1,L6" 식으로 좁힐 수 있다 (run_gpustack_custom.sh 파리티).
LEVELS="${5:-}"

if [ ! -d "$KOA_DIR" ]; then
  echo "ERROR: $KOA_DIR 없음. 먼저 install.sh 실행."
  exit 1
fi

# ── sampling 제약 감지 ────────────────────────────────────────────────────
# passk 는 --temperature 와 반복별 seed 로 "지정한 조건에서의" 반복 안정성을
# 재려는 트랙이다. 그런데 서빙 백엔드가 이 둘을 거부하면(vLLM diffusion 등)
# shared/serving/constraints.py 가 페이로드에서 아예 제거한다. 그러면:
#
#   - $TEMP 인자가 무시된다 → 0.3 이든 0.7 이든 서버 기본 샘플링으로만 돈다.
#     즉 "temperature 를 바꿔가며 비교"가 불가능하다.
#   - seed 가 무시된다 → 같은 런을 재현할 수 없다.
#
# 다만 반복 자체가 무의미해지는 것은 아니다. 실측(DiffusionGemma-26B, L6 15태스크
# ×2반복): temperature/seed 제거 상태에서도 15/15 태스크의 응답이 반복마다 달랐다.
# 즉 모델 고유의 비결정성은 남아 있어 분산 측정은 여전히 성립한다.
# 그래서 막지 않고 경고만 한다. 자동화 파이프라인에서 확실히 차단하려면
# AGENT_PASSK_STRICT=1 로 실패시킬 수 있다.
#
# 모델별 목록을 관리하지 않고 제약 자체를 본다. 앞으로 추가될 제약 백엔드도
# 같은 env 를 쓰므로 자동으로 걸린다. 이 env 는 configs/load_model_config.py 를
# source 해야 채워진다.
_blocked=""
for _p in temperature seed; do
  case ",${SERVING_UNSUPPORTED_SAMPLING_PARAMS:-}," in
    *",$_p,"*) _blocked="${_blocked:+$_blocked, }$_p" ;;
  esac
done
if [ -n "$_blocked" ]; then
  echo "[passk] 경고: 서빙 백엔드가 [$_blocked] 를 거부한다 (constraints 가 제거)."
  case ",${SERVING_UNSUPPORTED_SAMPLING_PARAMS:-}," in
    *",temperature,"*)
      echo "[passk]   → TEMP=$TEMP 인자가 무시된다. 서버 기본 샘플링으로 돈다." ;;
  esac
  case ",${SERVING_UNSUPPORTED_SAMPLING_PARAMS:-}," in
    *",seed,"*)
      echo "[passk]   → 반복별 seed 가 무시된다. 이 런은 재현 불가능하다." ;;
  esac
  echo "[passk]   반복 간 분산은 모델 고유 비결정성만 반영한다. 해석에 주의."
  if [ "${AGENT_PASSK_STRICT:-0}" = "1" ]; then
    echo "ERROR: AGENT_PASSK_STRICT=1 이므로 중단한다." >&2
    exit 1
  fi
fi

# 커스텀 파일 복사 (run_gpustack_custom.sh 와 동일 집합·동일 규칙)
# cp -u 를 쓰지 않는다: vendored 는 install.sh 가 덮어쓰는 영역이라 mtime 비교로
# 건너뛰면 옛 사본이 남는다. 원본을 항상 강제 반영한다.
cp "$SCRIPT_DIR/gpustack_custom/run_gpustack_benchmark_with_logging.py" \
   "$KOA_DIR/run_gpustack_benchmark_with_logging.py"
cp "$SCRIPT_DIR/gpustack_custom/openai_compat_adapter.py" \
   "$KOA_DIR/bench/adapters/openai_compat_adapter.py"
# adapter 가 import 하는 reasoning 모듈도 함께 복사 (없으면 ModuleNotFoundError)
cp "$SCRIPT_DIR/gpustack_custom/reasoning.py" \
   "$KOA_DIR/bench/adapters/reasoning.py"
# adapter 가 import 하는 파서 (없으면 ImportError — passk 단독 실행 시 실제로 터진다)
cp "$SCRIPT_DIR/gpustack_custom/tool_call_parser.py" \
   "$KOA_DIR/bench/adapters/tool_call_parser.py"
cp "$SCRIPT_DIR/gpustack_custom/run_ko-agentbench-passk.sh" \
   "$KOA_DIR/run_ko-agentbench-passk.sh"

cd "$KOA_DIR"
bash run_ko-agentbench-passk.sh "$MODEL" "$BASE_URL" "$TEMP" "$REPS" "$LEVELS"

SCORING_TS="${EVAL_TIMESTAMP:-}"
if [ -z "$SCORING_TS" ] && [ -f "$BASE_DIR/.eval_session" ]; then
  SCORING_TS="$(cat "$BASE_DIR/.eval_session")"
fi
# inner 스크립트가 --track-name agent_passk 를 고정하므로 채점 트랙도 고정한다.
SCORING_TRACK="${AGENT_PASSK_TRACK_NAME:-agent_passk}"
PY="${PY:-$BASE_DIR/.venv/bin/python}"

"$PY" "$SCRIPT_DIR/scoring/score_run.py" \
  --model "$MODEL" \
  --timestamp "$SCORING_TS" \
  --track "$SCORING_TRACK" \
  || echo "[agent-scoring] 실패 — 계속"
