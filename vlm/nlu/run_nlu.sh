#!/usr/bin/env bash

# Usage:
#   ./run_nlu.sh [--model MODEL] [--prompt PROMPT_FILE] [--endpoint ENDPOINT]
#   ./run_nlu.sh --model MODEL            # runs all prompts in ./prompt/*.yaml
#
# 예시:
#   ./run_nlu.sh                    # 기본 모델, 기본/전체 프롬프트
#   ./run_nlu.sh --model qwen3-vl-8b-instruct
#   ./run_nlu.sh --model qwen3-vl-8b-instruct --endpoint http://172.16.1.81:18090/v1/chat/completions --prompt prompt/jjajangmyeon.yaml

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODEL=""
PROMPT_FILE=""
ENDPOINT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      MODEL="${2:-}"; shift 2 ;;
    --prompt)
      PROMPT_FILE="${2:-}"; shift 2 ;;
    --endpoint)
      ENDPOINT="${2:-}"; shift 2 ;;
    -h|--help)
      python "$SCRIPT_DIR/nlu-gpustack.py" --help; exit 0 ;;
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

python "$SCRIPT_DIR/nlu-gpustack.py" "${ARGS[@]}"

