#!/usr/bin/env bash
# 저장된 agent summary에서 모델별 대표 run의 레벨 점수를 보고한다.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/foundation_model_test_non_thinking/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "[agent-levels] FAIL Python not found: $PYTHON" >&2
  exit 1
fi

exec "$PYTHON" "$ROOT_DIR/report_agent_levels.py" "$@"
