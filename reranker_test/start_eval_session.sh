#!/bin/bash
# 평가 세션 시작 — timestamp 명시 또는 현재 시각으로 .eval_session 작성
# 참조 model_test/start_eval_session.sh 와 동일 동작.
#
# Usage:
#   ./start_eval_session.sh                    # 현재 시각으로 시작
#   ./start_eval_session.sh 20260628_153000    # 명시 timestamp

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_FILE="$SCRIPT_DIR/.eval_session"

TS="${1:-$(date +%Y%m%d_%H%M%S)}"

if [ -f "$SESSION_FILE" ]; then
  OLD_TS=$(cat "$SESSION_FILE")
  echo "[start_eval_session] WARN: 기존 세션 ($OLD_TS) 덮어씌움"
fi

echo "$TS" > "$SESSION_FILE"
echo "[start_eval_session] 세션 시작: $TS"
echo "  결과 폴더: results/<safe_model>/$TS/reranker/<track>/<bench>/summary.json"
echo "  세션 종료: ./end_eval_session.sh"
