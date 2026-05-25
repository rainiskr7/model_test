#!/bin/bash

# Usage:
#   ./run_harness.sh [MODEL_NAME [TOKENIZER [BASE_URL]]]
#   - MODEL_NAME: lm_eval --model_args 의 model 값 (기본: qwen3-vl-8b-instruct)
#   - TOKENIZER : lm_eval --model_args 의 tokenizer 값 (기본: Qwen/Qwen3-VL-8B-Instruct, 허깅페이스에서 다운로드)
#   - BASE_URL  : lm_eval --model_args 의 base_url 값 (기본: http://172.16.1.81:18090/v1/chat/completions)
#
# 평가 모드: chat-tuned 모델 가정 → /v1/chat/completions + chat template + 5-shot
#   instruct/chat 변종 아닌 base 모델이면 LM_EVAL_MODE=completions 환경변수로 변경 가능 (logprob).
#
# 결과 경로: <MODEL_TEST_BASE>/results/<safe_model>/<timestamp>/language/harness/<task>.json
#   - MODEL_TEST_BASE  env: 미설정 시 스크립트 위치 기준 ../.. 로 자동 추정
#   - EVAL_TIMESTAMP   env: 미설정 시 현재 시각으로 자동 생성
#
# Example:
# ./run_harness.sh
# ./run_harness.sh qwen3-vl-8b-instruct
# ./run_harness.sh qwen3-vl-8b-instruct Qwen/Qwen3-VL-8B-Instruct
# ./run_harness.sh qwen3-vl-8b-instruct Qwen/Qwen3-VL-8B-Instruct http://172.16.1.81:18090/v1/chat/completions

MODEL_NAME="${1:-qwen3-vl-8b-instruct}"
TOKENIZER="${2:-Qwen/Qwen3-VL-8B-Instruct}"
BASE_URL="${3:-http://172.16.1.81:18090/v1/chat/completions}"
LM_EVAL_MODE="${LM_EVAL_MODE:-chat}"  # chat | completions
NUM_FEWSHOT="${NUM_FEWSHOT:-5}"
# 메모리·truncation 안전 default (KMMLU 5-shot prompt 가 2047 초과 → max_length=4096 권장)
MAX_LENGTH="${MAX_LENGTH:-4096}"
BATCH_SIZE="${BATCH_SIZE:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# safe_model_name: replace '/', '-', ':' with '_'
SAFE_MODEL="${MODEL_NAME//\//_}"
SAFE_MODEL="${SAFE_MODEL//-/_}"
SAFE_MODEL="${SAFE_MODEL//:/_}"

# Timestamp 결정: EVAL_TIMESTAMP env > .eval_session 파일 > 새로 생성 + 저장
if [ -n "${EVAL_TIMESTAMP:-}" ]; then
  TIMESTAMP="$EVAL_TIMESTAMP"
elif [ -f "$BASE_DIR/.eval_session" ]; then
  TIMESTAMP="$(cat "$BASE_DIR/.eval_session")"
else
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
  echo "$TIMESTAMP" > "$BASE_DIR/.eval_session"
  echo "[eval_session] 새 세션 생성: $TIMESTAMP"
fi

RESULTS_DIR="$BASE_DIR/results/$SAFE_MODEL/$TIMESTAMP/language/harness"
mkdir -p "$RESULTS_DIR"

echo "[harness] BASE=$BASE_DIR"
echo "[harness] RESULTS_DIR=$RESULTS_DIR"

# 필요한 벤치마크만 주석 해제해 사용
TASKS=(
    # KMMLU : 45개 분야 벤치마크.
    kmmlu
    ## 참고: 빠른 검증을 위해 지주책무에서는 법률/문서 관련 8개 분야만 테스트 예정.
    ### 특정 분야만 테스트할 경우 아래와 같이 kmmlu_분야명 명시
    # kmmlu_law
    # kmmlu_criminal_law
    # kmmlu_patent
    # kmmlu_economics
    # kmmlu_accounting
    # kmmlu_management
    # kmmlu_taxation
    # kmmlu_real_estate

    # KOBEST : 종합적인 한국어 이해 및 논리적 사고 능력 평가
    # kobest

    # CLICK : 문화, 언어 지식 평가
    # click

    # HAERAE : 한국 문화적, 맥락적 뉘앙스 이해 검증
    # haerae

    # KBL : 법률 이해
    # kbl
)

if [ "$LM_EVAL_MODE" = "chat" ]; then
  # local-chat-completions 는 logprob 미지원 → multiple-choice (KMMLU 등) 평가 불가
  # 대신 local-completions + apply_chat_template: prompt 에 chat template 박은 채 /v1/completions 호출
  # /v1/completions 는 logprob 반환 → multiple-choice OK
  LM_MODEL="local-completions"
  EXTRA_ARGS=(--apply_chat_template --num_fewshot "$NUM_FEWSHOT")
  if [[ "$BASE_URL" == */chat/completions ]]; then
    BASE_URL="${BASE_URL%/chat/completions}/completions"
    echo "[harness] base_url 자동 보정 → $BASE_URL"
  fi
else
  LM_MODEL="local-completions"
  EXTRA_ARGS=()
fi
echo "[harness] mode=$LM_EVAL_MODE model_type=$LM_MODEL fewshot=$NUM_FEWSHOT"

for TASK in "${TASKS[@]}"
do
  echo "Running task: $TASK"

  lm_eval \
    --model "$LM_MODEL" \
    --tasks $TASK \
    --model_args model="${MODEL_NAME}",base_url="${BASE_URL}",tokenizer_backend=huggingface,tokenizer="${TOKENIZER}",num_concurrent=1,max_retries=3,max_length=${MAX_LENGTH} \
    --batch_size "$BATCH_SIZE" \
    "${EXTRA_ARGS[@]}" \
    --output_path "$RESULTS_DIR/${TASK}.json"

done
