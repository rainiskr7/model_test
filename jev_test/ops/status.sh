#!/bin/bash
# 무엇: 읽기 전용 수량 관측. 입력: model run_id. 출력: 원문 없는 TSV 표.
source "$(dirname "$0")/lib.sh"
[ "$#" = 2 ] && identifier "$1" && identifier "$2" || exit 2
if dry; then show "$PY" -I -B -c "$HELPER" ops/status.py "$@"; exit 0; fi
helper status "$@"
