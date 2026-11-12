#!/bin/bash
# K-MMBench (NCSOFT) — 한국어 멀티모달 4,329 샘플 (dev). 카테고리 선별 옵션 지원.
# Usage:
#   ./run_k_mmbench.sh MODEL [BASE_URL]
#   ./run_k_mmbench.sh MODEL [BASE_URL] --categories cat1,cat2,...
#
# plan #2 권장: 표·차트·영수증·표지판 카테고리 선별 (필요 시 첫 실행 후 적합 카테고리 선택)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL="${1:?'MODEL required: ./run_k_mmbench.sh MODEL [BASE_URL] [--categories ...]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"
# shift 만큼만 안전하게 (인자 부족 시 fail 방지)
if (($# >= 2)); then shift 2; else shift "$#"; fi

# K_MMBENCH_TIMEOUT env 로 요청 timeout 조정 (default 60 — 미설정이면 --timeout 을 생략해
# Python CLI 기본값과 기존 호출 인자를 유지). 설정값은 양의 유한 숫자만 허용한다.
TIMEOUT_ARGS=()
if [ "${K_MMBENCH_TIMEOUT+set}" = set ]; then
  if ! [[ "$K_MMBENCH_TIMEOUT" =~ ^[+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$ ]] ||
     ! LC_ALL=C awk 'BEGIN { n = ARGV[1] + 0; exit !(n > 0 && n <= 1.7976931348623157e308) }' "$K_MMBENCH_TIMEOUT"; then
    echo "[k_mmbench] K_MMBENCH_TIMEOUT must be a positive finite number" >&2
    exit 2
  fi
  TIMEOUT_ARGS=(--timeout "$K_MMBENCH_TIMEOUT")
fi

cd "$SCRIPT_DIR/benches"
PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}" python -m shared.multimodal.benches.k_mmbench --model "$MODEL" --base-url "$BASE_URL" "${TIMEOUT_ARGS[@]}" "$@"
