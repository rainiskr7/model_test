#!/bin/bash
# K-DTCBench (NCSOFT) — 한국어 문서/표/차트 multiple-choice VQA, 240 샘플
# Usage: ./run_k_dtcbench.sh MODEL [BASE_URL]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL="${1:?'MODEL required: ./run_k_dtcbench.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

# K_DTCBENCH_TIMEOUT env 로 요청 timeout 조정 (default 60 — 미설정이면 --timeout 을 생략해
# Python CLI 기본값과 기존 호출 인자를 유지). 설정값은 양의 유한 숫자만 허용한다.
TIMEOUT_ARGS=()
if [ "${K_DTCBENCH_TIMEOUT+set}" = set ]; then
  if ! [[ "$K_DTCBENCH_TIMEOUT" =~ ^[+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$ ]] ||
     ! LC_ALL=C awk 'BEGIN { n = ARGV[1] + 0; exit !(n > 0 && n <= 1.7976931348623157e308) }' "$K_DTCBENCH_TIMEOUT"; then
    echo "[k_dtcbench] K_DTCBENCH_TIMEOUT must be a positive finite number" >&2
    exit 2
  fi
  TIMEOUT_ARGS=(--timeout "$K_DTCBENCH_TIMEOUT")
fi

cd "$SCRIPT_DIR/benches"
PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}" python -m shared.multimodal.benches.k_dtcbench --model "$MODEL" --base-url "$BASE_URL" "${TIMEOUT_ARGS[@]}"
