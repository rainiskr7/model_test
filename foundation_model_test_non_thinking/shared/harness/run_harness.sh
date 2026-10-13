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

# **빈 문자열은 "미지정"이 아니라 "빈 값"이다.** 아래 `${2:-...}` 의 `:-` 는
# 인자가 없을 때뿐 아니라 **비어 있을 때도** 기본값으로 바꾼다. 그래서 config 의
# `tokenizer_path` 가 빈 문자열이면 조용히 Qwen 토크나이저로 대체되고,
# **다른 모델의 토크나이저로 채점한 결과가 성공한 것처럼 나온다.**
# 기본값이 적용되기 **전에** 판정해야 한다.
if [ "$#" -ge 2 ] && [ -z "$2" ]; then
  echo "run_harness.sh: TOKENIZER 가 빈 문자열이다 — 기본값으로 대체하지 않는다." >&2
  echo "  모델 config 의 tokenizer_path 를 채우거나 두 번째 인자로 넘겨라." >&2
  exit 2
fi

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
  # completions 모드: chat template 미적용(raw). thinking 모델의 template 오염 회피.
  #   ⚠️ --num_fewshot 는 반드시 명시 — 미지정 시 KMMLU task 디폴트(0-shot)로 떨어져
  #      5-shot 결과와 비교 불가. (완주 실측: chat=0.000 → completions+5shot=0.540)
  LM_MODEL="local-completions"
  EXTRA_ARGS=(--num_fewshot "$NUM_FEWSHOT")
  if [[ "$BASE_URL" == */chat/completions ]]; then
    BASE_URL="${BASE_URL%/chat/completions}/completions"
    echo "[harness] base_url 자동 보정 → $BASE_URL"
  fi
fi
echo "[harness] mode=$LM_EVAL_MODE model_type=$LM_MODEL fewshot=$NUM_FEWSHOT num_concurrent=$NUM_CONCURRENT"

# Cancellation/validation helpers are local to this repository.
source "$SCRIPT_DIR/harness_lib.sh" || exit 4
FAILED_TASKS=()
LM_PID="" TASK="" HARNESS_TMP_DIR="" CANCELLING=0 PRESERVE_TMP=0
harness_lock "$RESULTS_DIR/.harness.lock" || exit $?
trap 'harness_on_signal 143' TERM
trap 'harness_on_signal 130' INT
trap 'harness_cleanup_tmp' EXIT

for TASK in "${TASKS[@]}"; do
  if compgen -G "$RESULTS_DIR/${TASK}_*.json" >/dev/null; then
    existing=$(ls -1 "$RESULTS_DIR/${TASK}_"*.json | head -1)
    echo "[skip] $TASK: $existing 이미 존재"
    continue
  fi
  if ! harness_recover_task "$TASK"; then
    FAILED_TASKS+=("${TASK}(preserve_failed)")
    continue
  fi
  echo "Running task: $TASK"
  PRESERVE_TMP=0
  HARNESS_TMP_DIR=$(mktemp -d "$RESULTS_DIR/.tmp_${TASK}.XXXXXX") || {
    FAILED_TASKS+=("${TASK}(temp_failed)"); continue;
  }
  lm_eval \
    --model "$LM_MODEL" \
    --tasks "$TASK" \
    --model_args "model=${MODEL_NAME},base_url=${BASE_URL},tokenizer_backend=huggingface,tokenizer=${TOKENIZER},num_concurrent=${NUM_CONCURRENT},max_retries=3,max_length=${MAX_LENGTH}" \
    --batch_size "$BATCH_SIZE" \
    "${EXTRA_ARGS[@]}" \
    --output_path "$HARNESS_TMP_DIR/${TASK}.json" </dev/null 9>&- &
  LM_PID=$!
  wait "$LM_PID"; rc=$?; LM_PID=""
  if [ "$rc" -ne 0 ]; then
    FAILED_TASKS+=("${TASK}(rc=$rc)")
    echo "[WARN] failed: $TASK rc=$rc" >&2
    PRESERVE_TMP=1
  else
    outputs=()
    for output in "$HARNESS_TMP_DIR/${TASK}_"*.json; do
      [ -f "$output" ] && outputs+=("$output")
    done
    if [ "${#outputs[@]}" -ne 1 ]; then
      reason="output_count:${#outputs[@]}"
      FAILED_TASKS+=("${TASK}(invalid_output:$reason)")
      echo "[WARN] $TASK: invalid_output:$reason" >&2
      PRESERVE_TMP=1
    elif ! reason=$(harness_validate_structure "${outputs[0]}" "$TASK"); then
      FAILED_TASKS+=("${TASK}(invalid_output:$reason)")
      echo "[WARN] $TASK: invalid_output:$reason" >&2
      PRESERVE_TMP=1
    # 이 러너는 lm_eval 에 --limit 을 넘기지 않는다 → 기대값은 항상 "없음".
    #   환경의 LIMIT(일반적인 이름)을 쓰면 export 된 값 하나로 모든 과목이 거부된다.
    elif ! reason=$(harness_validate_run_limit "${outputs[0]}" ""); then
      FAILED_TASKS+=("${TASK}(invalid_output:$reason)")
      echo "[WARN] $TASK: invalid_output:$reason" >&2
      PRESERVE_TMP=1
    elif ! mv "${outputs[0]}" "$RESULTS_DIR/"; then
      FAILED_TASKS+=("${TASK}(move_failed)")
      echo "[WARN] $TASK: move_failed" >&2
      PRESERVE_TMP=1
    fi
  fi
  harness_cleanup_tmp
done
if ((${#FAILED_TASKS[@]} > 0)); then
  printf '[WARN] failed tasks (%d): %s\n' "${#FAILED_TASKS[@]}" "${FAILED_TASKS[*]}" >&2
  exit 1
fi
exit 0
