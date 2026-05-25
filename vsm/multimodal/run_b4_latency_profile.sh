#!/bin/bash
# Track B-4 — Latency profiling
# 조건별(text-only, 256px, 1024px, multi-image) 지연시간 측정. TTFT + 총 응답시간 + tokens/sec.
# Usage: ./run_b4_latency_profile.sh MODEL [BASE_URL] [REPS]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_b4_latency_profile.sh MODEL [BASE_URL] [REPS]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
REPS="${3:-50}"
# bash 'shift N' 은 $# < N 이면 하나도 안 옮기고 실패 → run_all.sh 가 2개만 줄 때 $@ 에
# MODEL+BASE_URL 가 남아 b4_latency_profile.py 로 위치인자 재주입돼 argparse 실패.
shift $(( $# < 3 ? $# : 3 ))

cd "$SCRIPT_DIR/benches"
python b4_latency_profile.py --model "$MODEL" --base-url "$BASE_URL" --reps "$REPS" "$@"
