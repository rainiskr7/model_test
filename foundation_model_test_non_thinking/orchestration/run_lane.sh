#!/bin/bash
# Invoke through orchestration/lanes/<name>.sh; do not resolve the symlink.
set -u
bad() { printf 'run_lane: %s\n' "$*" >&2; exit 2; }
[ "$#" -eq 0 ] || bad 'arguments are not supported'
lane=$(basename "$0" .sh)
HERE=$(cd "$(dirname "$0")/.." && pwd) || exit 2
BASE=$(cd "$HERE/.." && pwd) || exit 2
conf=$HERE/lanes/$lane.conf
CONFIG= HOST_ENV= HOST_DEFAULT= KEYVAR= TRACK= SESSION= LABEL= LANE_TOKENIZER=
PREFIX= STOP_LABEL= END_LABEL=
REPS=3 REQUIRE_NOTHINK=1 LM_EVAL_MODE=chat NUM_CONCURRENT=8
TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini
TAUBENCH_TRIALS=4 TAUBENCH_MAX_CONCURRENCY=4 AGENT_REQUEST_TIMEOUT=300
FULL_KRETA_WORKERS=4 FULL_KRETA_RESUME=0 FULL_RESUME_FROM=
FULL_AGENT_TASK_TIMEOUT=900
[ -f "$conf" ] || bad "missing conf: $conf"
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue ;; *=*) ;; *) bad "expected key=value: $line" ;; esac
  key=${line%%=*}; value=${line#*=}
  # Optional enclosing quotes are literal delimiters, never shell evaluation.
  case "$value" in \"*\") value=${value#\"}; value=${value%\"} ;; \'*\') value=${value#\'}; value=${value%\'} ;; esac
  case "$key" in
    CONFIG) CONFIG=$value ;; HOST_ENV) HOST_ENV=$value ;; HOST_DEFAULT) HOST_DEFAULT=$value ;;
    KEYVAR) KEYVAR=$value ;; TRACK) TRACK=$value ;; SESSION) SESSION=$value ;; LABEL) LABEL=$value ;;
    PREFIX) PREFIX=$value ;; STOP_LABEL) STOP_LABEL=$value ;; END_LABEL) END_LABEL=$value ;;
    REPS) REPS=$value ;; LANE_TOKENIZER) LANE_TOKENIZER=$value ;; REQUIRE_NOTHINK) REQUIRE_NOTHINK=$value ;;
    LM_EVAL_MODE) LM_EVAL_MODE=$value ;; NUM_CONCURRENT) NUM_CONCURRENT=$value ;;
    TAUBENCH_USER_MODEL) TAUBENCH_USER_MODEL=$value ;; TAUBENCH_TRIALS) TAUBENCH_TRIALS=$value ;;
    TAUBENCH_MAX_CONCURRENCY) TAUBENCH_MAX_CONCURRENCY=$value ;; AGENT_REQUEST_TIMEOUT) AGENT_REQUEST_TIMEOUT=$value ;;
    AGENT_TASK_TIMEOUT) FULL_AGENT_TASK_TIMEOUT=$value ;;
    KRETA_WORKERS) FULL_KRETA_WORKERS=$value ;; KRETA_RESUME) FULL_KRETA_RESUME=$value ;;
    RESUME_FROM) FULL_RESUME_FROM=$value ;;
    *) bad "unknown key: $key" ;;
  esac
done < "$conf"
for key in CONFIG HOST_ENV HOST_DEFAULT KEYVAR TRACK SESSION LABEL PREFIX END_LABEL; do
  [ -n "${!key}" ] || bad "required key: $key"
done
case "$HOST_ENV:$KEYVAR" in *[!a-zA-Z0-9_:]*|[0-9]*|*:[0-9]*) bad 'invalid environment variable name' ;; esac
# TRACK=full helpers. Existing tracks do not call these functions.
full_stage_index() {
  # Map the public resume stage name to its execution order.
  case "$1" in
    nlu) FULL_INDEX=1 ;; functionchat) FULL_INDEX=2 ;; taubench) FULL_INDEX=3 ;;
    multimodal) FULL_INDEX=4 ;; functionchat_judge) FULL_INDEX=5 ;;
    koffvqa_judge) FULL_INDEX=6 ;; derive) FULL_INDEX=7 ;;
    *) bad "invalid resume stage: $1" ;;
  esac
}

full_validate() {
  # Validate before activation, credential reads, or any fixture/server access.
  [ -n "$STOP_LABEL" ] || bad 'required key: STOP_LABEL'
  case "$REPS" in ''|*[!0-9]*) bad 'REPS must be positive' ;; esac
  [ "$REPS" -gt 0 ] 2>/dev/null || bad 'REPS must be positive'
  # Full-only: keep inherited AGENT_TASK_TIMEOUT untouched on legacy tracks.
  [ "$AGENT_REQUEST_TIMEOUT" -gt 0 ] 2>/dev/null || bad 'AGENT_REQUEST_TIMEOUT must be a positive integer'
  [ "$FULL_AGENT_TASK_TIMEOUT" -gt "$AGENT_REQUEST_TIMEOUT" ] 2>/dev/null || bad 'AGENT_TASK_TIMEOUT must be an integer greater than AGENT_REQUEST_TIMEOUT'
  case "$FULL_KRETA_WORKERS" in [1-4]) ;; *) bad 'KRETA_WORKERS must be 1..4' ;; esac
  case "$FULL_KRETA_RESUME" in 0|1) ;; *) bad 'KRETA_RESUME must be 0 or 1' ;; esac
  FULL_RESUME_REP=0 FULL_RESUME_INDEX=0
  if [ -n "$FULL_RESUME_FROM" ]; then
    [[ "$FULL_RESUME_FROM" =~ ^r([1-9][0-9]*):([a-z_]+)$ ]] || bad 'invalid RESUME_FROM'
    FULL_RESUME_REP=${BASH_REMATCH[1]}
    full_stage_index "${BASH_REMATCH[2]}"
    FULL_RESUME_INDEX=$FULL_INDEX
    [ "$FULL_RESUME_REP" -le "$REPS" ] 2>/dev/null || bad 'RESUME_FROM exceeds REPS'
  fi
}

full_skip_resume() {
  # N and the stage index identify the portion already completed.
  full_stage_index "$1"
  [ "$N" -lt "$FULL_RESUME_REP" ] ||
    { [ "$N" -eq "$FULL_RESUME_REP" ] && [ "$FULL_INDEX" -lt "$FULL_RESUME_INDEX" ]; }
}

full_command() {
  # Assemble argv once for execution and dry-run. RD is symbolic in dry-run.
  local stage=$1 predfile=$2
  case "$stage" in
    nlu) FULL_CMD=(bash vsm/nlu/run_nlu.sh --model "$MODEL" --endpoint "$BASE_URL_CHAT") ;;
    functionchat)
      FULL_CMD=(env "AGENT_REQUEST_TIMEOUT=$AGENT_REQUEST_TIMEOUT" "AGENT_TASK_TIMEOUT=$FULL_AGENT_TASK_TIMEOUT"
        bash vsm/functionchat/run_functionchat.sh "$MODEL" "$BASE_URL_CHAT") ;;
    taubench)
      FULL_CMD=(env TAUBENCH_MODE=solo TAUBENCH_TRIALS=1 "TAUBENCH_MAX_CONCURRENCY=$TAUBENCH_MAX_CONCURRENCY"
        "AGENT_REQUEST_TIMEOUT=$AGENT_REQUEST_TIMEOUT" "AGENT_TASK_TIMEOUT=$FULL_AGENT_TASK_TIMEOUT"
        bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT") ;;
    multimodal)
      FULL_CMD=(env "KRETA_WORKERS=$FULL_KRETA_WORKERS")
      if [ "$N" -eq "$FULL_RESUME_REP" ] && [ "$FULL_RESUME_INDEX" -eq 4 ] && [ "$FULL_KRETA_RESUME" = 1 ]; then
        FULL_CMD+=(KRETA_RESUME=1)
      fi
      FULL_CMD+=(bash vsm/multimodal/run_all.sh "$MODEL" "$BASE_URL_V1") ;;
    functionchat_judge)
      FULL_CMD=(python -m shared.functionchat.judge.run_judge --results-dir "$RD/$TS/language/functionchat") ;;
    koffvqa_judge)
      FULL_CMD=(python -m shared.multimodal.benches.koffvqa_api_judge --predfile "$predfile"
        --target-model "$MODEL" --judge-model openai/gpt-4.1-mini
        --judge-base-url https://openrouter.ai/api/v1 --judge-api-key-env TAUBENCH_USER_API_KEY --seed 0) ;;
    derive)
      FULL_CMD=(python derive_multimodal_publish.py --base . --write
        --source "$RD/$TS/vision/multimodal/koffvqa_api_judge") ;;
  esac
}

full_command_text() {
  # Judge argv contains only the environment variable name, so no key masking is needed.
  local arg separator=
  for arg in "${FULL_CMD[@]}"; do
    printf '%s%s' "$separator" "$arg"
    separator=' '
  done
}

full_dry_run() {
  # Symbolic RD deliberately avoids results_model_dir and filesystem queries.
  local RD='<RD>' stage prefix
  N=1
  while [ "$N" -le "$REPS" ]; do
    TS="${SESSION}_r${N}"
    printf 'SESSION=%s\n' "$TS"
    for stage in $FULL_STAGES; do
      if full_skip_resume "$stage"; then printf 'SKIP=%s %s\n' "$TS" "$stage"; continue; fi
      full_command "$stage" "$RD/$TS/vision/multimodal/koffvqa/<latest *_gen.xlsx>"
      case "$stage" in *_judge|derive) prefix='COMMAND[if-exists]=' ;; *) prefix='COMMAND=' ;; esac
      printf '%s%s\n' "$prefix" "$(full_command_text)"
    done
    N=$((N + 1))
  done
}

full_stage_ready() {
  # Conditional judges inspect this session only; select newest workbook by mtime.
  local stage=$1 candidate judge_dir
  case "$stage" in
    functionchat_judge) [ -d "$RD/$TS/language/functionchat" ] ;;
    koffvqa_judge)
      FULL_PREDFILE=
      for candidate in "$RD/$TS/vision/multimodal/koffvqa/"*_gen.xlsx; do
        [ -f "$candidate" ] || continue
        if [ -z "$FULL_PREDFILE" ] || [ "$candidate" -nt "$FULL_PREDFILE" ]; then FULL_PREDFILE=$candidate; fi
      done
      [ -n "$FULL_PREDFILE" ] ;;
    derive)
      if [ "$N" -eq "$FULL_RESUME_REP" ] && [ "$FULL_RESUME_INDEX" -eq 7 ]; then
        judge_dir="$RD/$TS/vision/multimodal/koffvqa_api_judge"
        if [ -f "$judge_dir/results.json" ] && [ -f "$judge_dir/summary.json" ]; then return 0; fi
        log "[$TS] derive 재개 불가 — judge 산출 없음"
        # Returning false here would turn this error into a successful condition skip.
        exit 2
      fi
      [ "$FULL_KOFFVQA_RAN" = 1 ] ;;
    *) return 0 ;;
  esac
}

full_invoke() (
  # Clear inherited knobs inside the child; only argv's env entries reintroduce them.
  local stage=$1
  unset AGENT_REQUEST_TIMEOUT AGENT_TASK_TIMEOUT NUM_CONCURRENT TAUBENCH_MODE TAUBENCH_TRIALS
  unset TAUBENCH_MAX_CONCURRENCY KRETA_WORKERS KRETA_RESUME
  case "$stage" in
    *_judge|derive) PYTHONPATH="$BASE${PYTHONPATH:+:$PYTHONPATH}" EVAL_TIMESTAMP="$TS" "${FULL_CMD[@]}" ;;
    *) EVAL_TIMESTAMP="$TS" "${FULL_CMD[@]}" ;;
  esac
) 9>&-

full_run_stage() {
  # Record every executed stage and enforce stop/continue policy at one boundary.
  local stage=$1 rc
  if ! full_stage_ready "$stage"; then log "[$TS] $stage skip (condition)"; return; fi
  full_command "$stage" "$FULL_PREDFILE"
  log "[$TS] $stage 시작: $(full_command_text)"
  full_invoke "$stage" >>"$BASE/logs/$TS/$stage.log" 2>&1
  rc=$?
  log "[$TS] $stage 종료 rc=$rc"
  # Normal flow derives after judge rc 0; explicit derive resume checks saved files instead.
  if [ "$stage" = koffvqa_judge ] && [ "$rc" -eq 0 ]; then FULL_KOFFVQA_RAN=1; fi
  if [ "$rc" -eq 3 ] || [ "$rc" -ge 129 ]; then exit "$rc"; fi
  [ "$rc" -ne 0 ] || return 0
  case "$stage" in
    nlu|functionchat|multimodal)
      log "[$TS] $stage 실패 — $STOP_LABEL 레인 중단 (원인 확인 후 수동 재개)"
      exit "$rc" ;;
    taubench) log "[$TS] $stage 실패 rc=$rc — 계속" ;;
    *) FULL_JUDGE_FAILURES=$((FULL_JUDGE_FAILURES + 1)); log "[$TS] $stage 실패 rc=$rc — 계속" ;;
  esac
}

full_run() {
  # Resolve shared spelling once, then orchestrate ordered stages for each session.
  local safe_model model_dir stage
  source "$BASE/shared/results_dir.sh"
  safe_model=$(printf '%s' "$MODEL" | tr '/:-' '___')
  model_dir=$(results_model_dir "$BASE" "$safe_model") || exit "$?"
  RD="$BASE/results/$model_dir"
  FULL_JUDGE_FAILURES=0
  log "=== $LABEL 시작 MODEL=$MODEL host=$HOST sessions=${BASE_TS}_r1..r$REPS ==="
  N=1
  while [ "$N" -le "$REPS" ]; do
    TS="${BASE_TS}_r${N}" FULL_KOFFVQA_RAN=0 FULL_PREDFILE=
    if [ -z "$FULL_RESUME_FROM" ] && [ -e "$RD/$TS" ]; then
      log "[$TS] 세션 존재 — 재개는 RESUME_FROM"
      exit 2
    fi
    for stage in $FULL_STAGES; do
      if full_skip_resume "$stage"; then log "[$TS] $stage skip (resume)"; continue; fi
      mkdir -p "$BASE/logs/$TS"
      full_run_stage "$stage"
    done
    N=$((N + 1))
  done
  log "=== $END_LABEL 레인 종료 (판정 실패 ${FULL_JUDGE_FAILURES}건) ==="
  [ "$FULL_JUDGE_FAILURES" -eq 0 ] || exit 1
  exit 0
}

case "$TRACK" in
  kmmlu)
    [ -n "$LANE_TOKENIZER" ] || bad 'required key: LANE_TOKENIZER'
    [ -n "$STOP_LABEL" ] || bad 'required key: STOP_LABEL'
    case "$REPS" in ''|*[!0-9]*) bad 'REPS must be positive' ;; esac
    [ "$REPS" -gt 0 ] || bad 'REPS must be positive'
    case "$NUM_CONCURRENT" in [1-8]) ;; *) bad 'NUM_CONCURRENT must be 1..8' ;; esac
    case "$REQUIRE_NOTHINK" in 0|1) ;; *) bad 'REQUIRE_NOTHINK must be 0 or 1' ;; esac
    ;;
  full)
    FULL_STAGES="nlu functionchat taubench multimodal functionchat_judge koffvqa_judge derive"
    full_validate
    ;;
  taubench_std4) ;;
  *) bad "unknown TRACK: $TRACK" ;;
esac
cd "$BASE" || exit 1
source "$BASE/.venv/bin/activate"
export MODEL_TEST_BASE="$BASE"
if [ "$TRACK" = kmmlu ]; then export NUM_CONCURRENT LM_EVAL_MODE
elif [ "$TRACK" != full ]; then export TAUBENCH_MAX_CONCURRENCY; fi
ORCH="$BASE/logs/resume_orch"
HOST=${!HOST_ENV:-$HOST_DEFAULT}
TOK=$LANE_TOKENIZER
BASE_TS=$SESSION
read_key() { grep -E "^$1=" "$BASE/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }
# Dry-run never opens .env, writes logs, or performs preflight.
if [ "${LANE_DRY_RUN:-0}" != 1 ]; then
  export OPENAI_API_KEY="$(read_key "$KEYVAR")"
  if [ "$TRACK" = taubench_std4 ] || [ "$TRACK" = full ]; then export TAUBENCH_USER_API_KEY="$(read_key TAUBENCH_USER_API_KEY)"; fi
fi
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$ORCH/orchestrator.log"; }
export BASE_URL_CHAT_OVERRIDE=http://$HOST/v1/chat/completions
export BASE_URL_V1_OVERRIDE=http://$HOST/v1
loader=$(python "$BASE/configs/load_model_config.py" "$CONFIG" 2>/dev/null) || exit 1
eval "$loader"
if [ "${LANE_DRY_RUN:-0}" = 1 ]; then
  printf 'BASE=%s\nconf=%s\nHOST=%s\n' "$BASE" "$conf" "$HOST"
  if [ "$TRACK" = full ]; then
    full_dry_run
  elif [ "$TRACK" = kmmlu ]; then
    N=1
    while [ "$N" -le "$REPS" ]; do printf 'SESSION=%s_r%s\n' "$SESSION" "$N"; N=$((N + 1)); done
    printf 'COMMAND=bash vsm/harness/run_harness.sh %s %s %s\n' "$MODEL" "$TOK" "$BASE_URL_CHAT"
  else
    printf 'SESSION=%s\n' "$SESSION"
    printf 'COMMAND=env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL=%s TAUBENCH_TRIALS=%s AGENT_REQUEST_TIMEOUT=%s TAUBENCH_MAX_CONCURRENCY=%s bash vsm/taubench/run_taubench.sh %s %s\n' "$TAUBENCH_USER_MODEL" "$TAUBENCH_TRIALS" "$AGENT_REQUEST_TIMEOUT" "$TAUBENCH_MAX_CONCURRENCY" "$MODEL" "$BASE_URL_CHAT"
  fi
  exit 0
fi
mkdir -p "$ORCH" || { log "$PREFIX: 잠금 오류"; exit 4; }
source "$BASE/shared/harness/harness_lib.sh" || { log "$PREFIX: 잠금 오류"; exit 4; }
host_lock_name=${HOST//[^A-Za-z0-9._-]/_}
harness_lock "$ORCH/.lane_host_${host_lock_name}.lock" >/dev/null
lock_rc=$?
case "$lock_rc" in
  0) ;;
  3) log "$PREFIX: 같은 호스트 레인 실행 중 — 시작 안 함"; exit 2 ;;
  *) log "$PREFIX: 잠금 오류"; exit 4 ;;
esac
# Preserve the exact wording supplied by each lane's configuration.
if [ "$TRACK" = kmmlu ] && [ "$REQUIRE_NOTHINK" = 1 ]; then
  grep -q 'set enable_thinking = false' "$TOK/chat_template.jinja" || { log "$PREFIX: 생각 끈 사본이 아니다 — $TOK"; exit 1; }
fi
body="$(mktemp)"; code="$(curl -s -m 10 -o "$body" -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models")"
if [ "$code" != 200 ] || ! grep -q "\"id\":\"$MODEL\"" "$body"; then log "$PREFIX: preflight 실패 HTTP $code"; rm -f "$body"; exit 1; fi; rm -f "$body"
if [ "$TRACK" = full ]; then full_run; fi
if [ "$TRACK" = kmmlu ]; then
  log "=== $LABEL 시작 MODEL=$MODEL host=$HOST tok=$TOK sessions=${BASE_TS}_r1..r$REPS ==="
  N=1
  while [ "$N" -le "$REPS" ]; do
    TS="${BASE_TS}_r${N}"
    mkdir -p "$BASE/logs/$TS"
    log "[$TS] harness 시작: run_harness.sh $MODEL $TOK $BASE_URL_CHAT (LM_EVAL_MODE=$LM_EVAL_MODE)"
    ( EVAL_TIMESTAMP="$TS" bash vsm/harness/run_harness.sh "$MODEL" "$TOK" "$BASE_URL_CHAT" ) 9>&- >>"$BASE/logs/$TS/harness_${MODEL}.log" 2>&1
    rc=$?
    log "[$TS] harness 종료 rc=$rc"
    [ "$rc" -ne 0 ] && { log "[$TS] harness 실패 — $STOP_LABEL 레인 중단 (원인 확인 후 수동 재개)"; exit "$rc"; }
    N=$((N + 1))
  done
else
  TS=$SESSION
  log "=== $LABEL 시작 MODEL=$MODEL host=$HOST session=$TS ==="
  mkdir -p "$BASE/logs/$TS"
  log "[$TS] taubench_std4 시작: TAUBENCH_MODE=standard TRIALS=$TAUBENCH_TRIALS 동시 $TAUBENCH_MAX_CONCURRENCY 사용자 ${TAUBENCH_USER_MODEL##*/}"
  ( EVAL_TIMESTAMP="$TS" env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL="$TAUBENCH_USER_MODEL" \
      TAUBENCH_TRIALS="$TAUBENCH_TRIALS" AGENT_REQUEST_TIMEOUT="$AGENT_REQUEST_TIMEOUT" TAUBENCH_MAX_CONCURRENCY="$TAUBENCH_MAX_CONCURRENCY" \
      bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT" ) 9>&- >>"$BASE/logs/$TS/taubench_std4.log" 2>&1
  rc=$?
  log "[$TS] taubench_std4 종료 rc=$rc"
fi
log "=== $END_LABEL 레인 종료 ==="
[ "$TRACK" != taubench_std4 ] || exit "$rc"
