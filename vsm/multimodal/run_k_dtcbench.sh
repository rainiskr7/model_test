#!/bin/bash
# K-DTCBench (NCSOFT) — 한국어 문서/표/차트 multiple-choice VQA, 240 샘플
# Usage: ./run_k_dtcbench.sh MODEL [BASE_URL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_k_dtcbench.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

cd "$SCRIPT_DIR/benches"
python k_dtcbench.py --model "$MODEL" --base-url "$BASE_URL"
