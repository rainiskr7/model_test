#!/bin/bash
# Track B-3 — Structured Output (포맷 준수)
# 이미지 → JSON 변환 정확도 측정. 데이터: data/structured_output/manifest.json
# Usage: ./run_b3_structured_output.sh MODEL [BASE_URL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_b3_structured_output.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
# shift 만큼만 안전하게 (인자 부족 시 fail 방지)
if (($# >= 2)); then shift 2; else shift "$#"; fi

cd "$SCRIPT_DIR/benches"
python b3_structured_output.py --model "$MODEL" --base-url "$BASE_URL" "$@"
