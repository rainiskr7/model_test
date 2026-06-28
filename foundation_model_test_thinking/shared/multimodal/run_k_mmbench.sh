#!/bin/bash
# K-MMBench (NCSOFT) — 한국어 멀티모달 4,330 샘플 (dev). 카테고리 선별 옵션 지원.
# Usage:
#   ./run_k_mmbench.sh MODEL [BASE_URL]
#   ./run_k_mmbench.sh MODEL [BASE_URL] --categories cat1,cat2,...
#
# plan #2 권장: 표·차트·영수증·표지판 카테고리 선별 (필요 시 첫 실행 후 적합 카테고리 선택)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_k_mmbench.sh MODEL [BASE_URL] [--categories ...]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
# shift 만큼만 안전하게 (인자 부족 시 fail 방지)
if (($# >= 2)); then shift 2; else shift "$#"; fi

cd "$SCRIPT_DIR/benches"
python k_mmbench.py --model "$MODEL" --base-url "$BASE_URL" "$@"
