# Sourced by run_lane.sh; definitions only, using the common lane context.
# Inputs (phases: README.md): STOP_LABEL REPS AGENT_REQUEST_TIMEOUT FULL_AGENT_TASK_TIMEOUT
# FULL_KRETA_WORKERS FULL_KRETA_RESUME FULL_RESUME_FROM MODEL BASE_URL_CHAT BASE_URL_V1
# TAUBENCH_MAX_CONCURRENCY SESSION BASE PYTHONPATH LABEL HOST BASE_TS END_LABEL.
# Functions: bad read_key log; results_model_dir is sourced locally at run time.
track_secrets() { export TAUBENCH_USER_API_KEY="$(read_key TAUBENCH_USER_API_KEY)"; }

full_stage_index() {
  # Map the public resume stage name to its execution order.
  case "$1" in
    nlu) FULL_INDEX=1 ;; functionchat) FULL_INDEX=2 ;; taubench) FULL_INDEX=3 ;;
    multimodal) FULL_INDEX=4 ;; functionchat_judge) FULL_INDEX=5 ;;
    koffvqa_judge) FULL_INDEX=6 ;; derive) FULL_INDEX=7 ;;
    *) bad "invalid resume stage: $1" ;;
  esac
}

track_validate() {
  FULL_STAGES="nlu functionchat taubench multimodal functionchat_judge koffvqa_judge derive"
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

full_complete_command() {
  # A follow-up command within derive, not an additional resume stage.
  FULL_CMD=(python -m shared.multimodal.benches.koffvqa_judge_complete
    "$RD/$TS/vision/multimodal/koffvqa_api_judge")
}

track_dry_run() {
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
      if [ "$stage" = derive ]; then
        full_complete_command
        printf 'COMMAND[if-derive-rc=0]=%s\n' "$(full_command_text)"
      fi
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
      if [ -z "$FULL_PREDFILE" ] && [ "$N" -eq "$FULL_RESUME_REP" ] && [ "$FULL_RESUME_INDEX" -eq 6 ]; then
        log "[$TS] koffvqa_judge 재개 불가 — prediction xlsx 없음"
        exit 2
      fi
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
  if [ "$stage" = derive ] && [ "$rc" -eq 0 ]; then
    full_complete_command
    log "[$TS] derive 완전성 확인: $(full_command_text)"
    full_invoke "$stage" >>"$BASE/logs/$TS/$stage.log" 2>&1
    rc=$?
  fi
  log "[$TS] $stage 종료 rc=$rc"
  # rc 10 has saved artifacts too; derive preserves their publication rejection.
  if [ "$stage" = koffvqa_judge ] && { [ "$rc" -eq 0 ] || [ "$rc" -eq 10 ]; }; then FULL_KOFFVQA_RAN=1; fi
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

track_run() {
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
