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
NUM_CONCURRENT="${NUM_CONCURRENT:-1}"

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
    # KMMLU 45개. group 'kmmlu' 1회 호출은 evaluator 가 sub-task 결과를 끝까지 누적해 OOM 위험 → sub-task 단위 분리 호출.
    kmmlu_accounting
    kmmlu_agricultural_sciences
    kmmlu_aviation_engineering_and_maintenance
    kmmlu_biology
    kmmlu_chemical_engineering
    kmmlu_chemistry
    kmmlu_civil_engineering
    kmmlu_computer_science
    kmmlu_construction
    kmmlu_criminal_law
    kmmlu_ecology
    kmmlu_economics
    kmmlu_education
    kmmlu_electrical_engineering
    kmmlu_electronics_engineering
    kmmlu_energy_management
    kmmlu_environmental_science
    kmmlu_fashion
    kmmlu_food_processing
    kmmlu_gas_technology_and_engineering
    kmmlu_geomatics
    kmmlu_health
    kmmlu_industrial_engineer
    kmmlu_information_technology
    kmmlu_interior_architecture_and_design
    kmmlu_korean_history
    kmmlu_law
    kmmlu_machine_design_and_manufacturing
    kmmlu_management
    kmmlu_maritime_engineering
    kmmlu_marketing
    kmmlu_materials_engineering
    kmmlu_math
    kmmlu_mechanical_engineering
    kmmlu_nondestructive_testing
    kmmlu_patent
    kmmlu_political_science_and_sociology
    kmmlu_psychology
    kmmlu_public_safety
    kmmlu_railway_and_automotive_engineering
    kmmlu_real_estate
    kmmlu_refrigerating_machinery
    kmmlu_social_welfare
    kmmlu_taxation
    kmmlu_telecommunications_and_wireless_technology

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
echo "[harness] mode=$LM_EVAL_MODE model_type=$LM_MODEL fewshot=$NUM_FEWSHOT num_concurrent=$NUM_CONCURRENT"

FAILED_TASKS=()
HARNESS_TMP_DIR=""

# lm_eval semantics:
#   --output_path X.json  →  실제 파일은 X_<isotime>.json (loggers/evaluation_tracker.py:269-275)
# 따라서 task 단위 임시 dir 안에 lm_eval 실행시키고, 성공 시 생성된 ${TASK}_*.json 을
# RESULTS_DIR 로 이동. idempotency 도 같은 패턴 매칭으로 체크.
#
# SIGINT/SIGTERM/EXIT 시 진행 중이던 tmp dir 정리.
trap '[[ -n "$HARNESS_TMP_DIR" && -d "$HARNESS_TMP_DIR" ]] && rm -rf "$HARNESS_TMP_DIR"' INT TERM EXIT

for TASK in "${TASKS[@]}"
do
  # 이미 ${TASK}_<isotime>.json 결과 파일이 있으면 skip (부분 실패 후 재실행 시 시간 절약).
  if compgen -G "$RESULTS_DIR/${TASK}_*.json" > /dev/null; then
    existing=$(ls -1 "$RESULTS_DIR/${TASK}_"*.json | head -1)
    echo "[skip] $TASK: $existing 이미 존재"
    continue
  fi

  echo "Running task: $TASK"
  HARNESS_TMP_DIR="$RESULTS_DIR/.tmp_${TASK}"
  rm -rf "$HARNESS_TMP_DIR"
  mkdir -p "$HARNESS_TMP_DIR"

  if lm_eval \
    --model "$LM_MODEL" \
    --tasks "$TASK" \
    --model_args "model=${MODEL_NAME},base_url=${BASE_URL},tokenizer_backend=huggingface,tokenizer=${TOKENIZER},num_concurrent=${NUM_CONCURRENT},max_retries=3,max_length=${MAX_LENGTH}" \
    --batch_size "$BATCH_SIZE" \
    "${EXTRA_ARGS[@]}" \
    --output_path "$HARNESS_TMP_DIR/${TASK}.json"
  then
    # lm_eval 이 만든 ${TASK}_<isotime>.json (들) 을 정식 위치로 이동.
    if compgen -G "$HARNESS_TMP_DIR/${TASK}_*.json" > /dev/null; then
      mv "$HARNESS_TMP_DIR/${TASK}_"*.json "$RESULTS_DIR/"
    else
      # rc=0 인데 출력 파일이 없는 비정상 케이스 — 실패로 기록.
      FAILED_TASKS+=("${TASK}(no_output)")
      echo "[WARN] $TASK: lm_eval rc=0 but no output file produced" >&2
    fi
  else
    FAILED_TASKS+=("$TASK")
    echo "[WARN] failed: $TASK" >&2
  fi

  rm -rf "$HARNESS_TMP_DIR"
  HARNESS_TMP_DIR=""
done

if ((${#FAILED_TASKS[@]} > 0)); then
  printf '[WARN] failed tasks (%d): %s\n' "${#FAILED_TASKS[@]}" "${FAILED_TASKS[*]}" >&2
  exit 1
fi
