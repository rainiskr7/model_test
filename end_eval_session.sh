#!/bin/bash
# 현재 평가 세션 종료 (다음 평가 시 새 timestamp 폴더 시작)
#
# Usage:
#   ./end_eval_session.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_FILE="$SCRIPT_DIR/.eval_session"

if [ -f "$SESSION_FILE" ]; then
  OLD_TS=$(cat "$SESSION_FILE")
  rm "$SESSION_FILE"
  echo "[end_eval_session] 세션 종료: $OLD_TS"
  echo "  다음 평가는 새 timestamp 폴더 시작"
else
  echo "[end_eval_session] 활성 세션 없음 (이미 정리됨)"
fi
