#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run_nlu.sh [--model MODEL] [--prompt PROMPT_FILE] [--endpoint ENDPOINT] [--overwrite]
#   ./run_nlu.sh --model MODEL            # runs all prompts in ./prompt/*.yaml
#
# 예시:
#   ./run_nlu.sh                    # 기본 모델, 기본/전체 프롬프트
#   ./run_nlu.sh --model qwen3-vl-8b-instruct
#   ./run_nlu.sh --model qwen3-vl-8b-instruct --endpoint http://172.16.1.81:18090/v1/chat/completions --prompt prompt/jjajangmyeon.yaml

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 인터프리터 해석은 인자 검사 **뒤**에 한다 — 순서를 뒤집으면 인자 오류가
# 환경 오류에 가려진다.
resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 && { echo "$PYTHON_BIN"; return 0; }
    echo "run_nlu.sh: 인터프리터를 찾을 수 없다: $PYTHON_BIN" >&2
    return 127
  fi
  # 형제 트랙들이 쓰는 `python` 을 우선한다(같은 평가에서 인터프리터가 갈리지
  # 않도록). 다만 `python` 이 없는 환경이 실재한다 — 그 경우 python3 으로 간다.
  for candidate in python python3; do
    command -v "$candidate" >/dev/null 2>&1 && { echo "$candidate"; return 0; }
  done
  echo "run_nlu.sh: python / python3 을 모두 찾을 수 없다 (PYTHON_BIN 으로 지정하라)" >&2
  return 127
}

MODEL=""
PROMPT_FILE=""
ENDPOINT=""
OVERWRITE=""

# 값을 요구하는 옵션. `shift 2` 를 그냥 부르면 값이 없을 때 shift 가 실패하고
# 인자가 그대로 남아 while 루프가 영원히 돈다 — 평가 스크립트가 끝나지 않는다.
require_value() {
  if [[ $2 -lt 2 ]]; then
    echo "run_nlu.sh: $1 에 값이 필요하다" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      require_value "$1" $#; MODEL="$2"; shift 2 ;;
    --prompt)
      require_value "$1" $#; PROMPT_FILE="$2"; shift 2 ;;
    --endpoint)
      require_value "$1" $#; ENDPOINT="$2"; shift 2 ;;
    --overwrite)
      OVERWRITE=1; shift ;;
    -h|--help)
      # help 조차 실패할 수 있다(인터프리터/임포트). 종료코드를 삼키지 않는다.
      PYTHON_BIN="$(resolve_python)" || exit 127
      exec "$PYTHON_BIN" "$SCRIPT_DIR/nlu-gpustack.py" --help ;;
    *)
      # Backward-compatible positional args: [MODEL] [PROMPT_FILE] [ENDPOINT]
      if [[ -z "$MODEL" ]]; then
        MODEL="$1"; shift
      elif [[ -z "$PROMPT_FILE" ]]; then
        PROMPT_FILE="$1"; shift
      elif [[ -z "$ENDPOINT" ]]; then
        ENDPOINT="$1"; shift
      else
        echo "Unknown argument: $1" >&2
        exit 2
      fi
      ;;
  esac
done

ARGS=()
if [[ -n "$MODEL" ]]; then ARGS+=(--model "$MODEL"); fi
if [[ -n "$PROMPT_FILE" ]]; then ARGS+=(--prompt "$PROMPT_FILE"); fi
if [[ -n "$ENDPOINT" ]]; then ARGS+=(--endpoint "$ENDPOINT"); fi
if [[ -n "$OVERWRITE" ]]; then ARGS+=(--overwrite); fi

PYTHON_BIN="$(resolve_python)" || exit 127
exec "$PYTHON_BIN" "$SCRIPT_DIR/nlu-gpustack.py" ${ARGS[@]+"${ARGS[@]}"}
