#!/bin/bash
# MTVQA(KR) (ByteDance) — 9개 언어 중 한국어 서브셋, 실세계 장면 텍스트 free-form VQA.
# Usage: ./run_mtvqa_kr.sh MODEL [BASE_URL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:?'MODEL required: ./run_mtvqa_kr.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
# shift 만큼만 안전하게 (인자 부족 시 fail 방지)
if (($# >= 2)); then shift 2; else shift "$#"; fi

cd "$SCRIPT_DIR/benches"
python mtvqa_kr.py --model "$MODEL" --base-url "$BASE_URL" "$@"
