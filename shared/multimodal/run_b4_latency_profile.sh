#!/bin/bash
# Track B-4 — Latency profiling
# 조건별(text-only, 256px, 1024px, multi-image) 지연시간 측정. TTFT + 총 응답시간 + tokens/sec.
# Usage: ./run_b4_latency_profile.sh MODEL [BASE_URL] [REPS]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_b4_latency_profile.sh MODEL [BASE_URL] [REPS]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
REPS="${3:-50}"
# shift 만큼만 안전하게 (인자 2개여도 fail 하지 않도록)
if (($# >= 3)); then shift 3; else shift "$#"; fi

cd "$SCRIPT_DIR/benches"
python b4_latency_profile.py --model "$MODEL" --base-url "$BASE_URL" --reps "$REPS" "$@"
