#!/bin/bash
# vsm/multimodal 전체 비전 트랙 일괄 실행 (한 모델, 한 timestamp)
#
# Usage:
#   ./run_all.sh MODEL [BASE_URL]
#
# 결과 위치:
#   results/<safe_model>/<timestamp>/vision/multimodal/{kreta,k_dtcbench,k_mmbench,mtvqa_kr,koffvqa,ko_vlm_benchmark}/
#   results/<safe_model>/<timestamp>/vision/customB/{b3_structured_output,b4_latency_profile}/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_all.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

# 동일 timestamp 공유: EVAL_TIMESTAMP env > .eval_session 파일 > 새로 생성
if [ -z "${EVAL_TIMESTAMP:-}" ]; then
  if [ -f "$SCRIPT_DIR/../../.eval_session" ]; then
    export EVAL_TIMESTAMP="$(cat "$SCRIPT_DIR/../../.eval_session")"
  else
    export EVAL_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    echo "$EVAL_TIMESTAMP" > "$SCRIPT_DIR/../../.eval_session"
    echo "[eval_session] 새 세션 생성: $EVAL_TIMESTAMP"
  fi
fi
echo "[run_all] EVAL_TIMESTAMP=$EVAL_TIMESTAMP"
echo "[run_all] MODEL=$MODEL BASE_URL=$BASE_URL"

# 가장 가벼운 것부터
echo "=== K-DTCBench (240) ==="
bash "$SCRIPT_DIR/run_k_dtcbench.sh" "$MODEL" "$BASE_URL" || echo "[run_all] K-DTCBench 실패 — 계속"

echo "=== KOFFVQA (275, Rubric judge) ==="
bash "$SCRIPT_DIR/run_koffvqa.sh" "$MODEL" "$BASE_URL" || echo "[run_all] KOFFVQA 실패 — 계속"

echo "=== MTVQA-KR (한국어 서브셋) ==="
bash "$SCRIPT_DIR/run_mtvqa_kr.sh" "$MODEL" "$BASE_URL" || echo "[run_all] MTVQA-KR 실패 — 계속"

echo "=== K-MMBench (4,330) ==="
bash "$SCRIPT_DIR/run_k_mmbench.sh" "$MODEL" "$BASE_URL" || echo "[run_all] K-MMBench 실패 — 계속"

echo "=== KRETA ==="
bash "$SCRIPT_DIR/run_kreta.sh" "$MODEL" default "$BASE_URL" || echo "[run_all] KRETA 실패 — 계속"

# KO-VLM-Benchmark — stub (외부 코드 OpenAI-compat 미지원, 별도 작업 필요)
echo "=== KO-VLM-Benchmark (stub — skip) ==="
bash "$SCRIPT_DIR/run_ko_vlm_benchmark.sh" 2>&1 | head -3 || true

echo "=== B-4 Latency Profile (50 reps × 4 conditions) ==="
bash "$SCRIPT_DIR/run_b4_latency_profile.sh" "$MODEL" "$BASE_URL" || echo "[run_all] B-4 실패 — 계속"

echo "=== B-3 Structured Output (data/structured_output/manifest.json 필요) ==="
if [ -f "$SCRIPT_DIR/data/structured_output/manifest.json" ]; then
  bash "$SCRIPT_DIR/run_b3_structured_output.sh" "$MODEL" "$BASE_URL" || echo "[run_all] B-3 실패 — 계속"
else
  echo "[run_all] B-3 manifest 없음 — 스킵 (data/structured_output/ 채우면 활성화)"
fi

echo "[run_all] all benchmarks done"
