# Sourced by run_lane.sh; definitions only, using the common lane context.
# Inputs (phases: README.md): SESSION TAUBENCH_USER_MODEL TAUBENCH_TRIALS
# TAUBENCH_USER_PROVIDER TAUBENCH_USER_QUANTIZATIONS TAUBENCH_USER_REASONING_EFFORT TAUBENCH_USER_TEMPERATURE_MODE TAUBENCH_USER_BASE_URL
# AGENT_REQUEST_TIMEOUT TAUBENCH_MAX_CONCURRENCY MODEL BASE_URL_CHAT LABEL HOST
# BASE END_LABEL; functions: read_key log bad.
track_export() { export TAUBENCH_MAX_CONCURRENCY; }
track_secrets() { export TAUBENCH_USER_API_KEY="$(read_key TAUBENCH_USER_API_KEY)"; }

track_validate() {
  case "$TAUBENCH_USER_REASONING_EFFORT" in ''|none|low|medium|high) ;; *) bad 'TAUBENCH_USER_REASONING_EFFORT must be empty, none, low, medium or high' ;; esac
  case "${TAUBENCH_USER_TEMPERATURE_MODE:-}" in ''|omit) ;; *) bad 'TAUBENCH_USER_TEMPERATURE_MODE must be empty or omit' ;; esac
  if [ -n "$TAUBENCH_USER_PROVIDER" ]; then
    [[ "$TAUBENCH_USER_PROVIDER" =~ ^[a-z0-9][a-z0-9/_.-]*$ ]] || bad 'TAUBENCH_USER_PROVIDER must match [a-z0-9][a-z0-9/_.-]*'
  fi
  if [ -n "$TAUBENCH_USER_QUANTIZATIONS" ]; then
    local quantization quant_seen=, quant_tokens=()
    local quant_allowed='int4,int8,fp4,mxfp4,nvfp4,fp6,fp8,mxfp8,fp16,bf16,fp32,unknown'
    [[ "$TAUBENCH_USER_QUANTIZATIONS" =~ ^[a-z0-9]+(,[a-z0-9]+)*$ ]] || bad 'TAUBENCH_USER_QUANTIZATIONS must be a comma-separated token list'
    IFS=, read -r -a quant_tokens <<< "$TAUBENCH_USER_QUANTIZATIONS"
    for quantization in "${quant_tokens[@]}"; do
      [[ ",$quant_allowed," == *",$quantization,"* ]] || bad "unsupported user quantization: $quantization"
      [[ "$quant_seen" != *",$quantization,"* ]] || bad "duplicate user quantization: $quantization"
      quant_seen+="$quantization,"
    done
  fi
  if [ -n "$TAUBENCH_USER_PROVIDER$TAUBENCH_USER_REASONING_EFFORT$TAUBENCH_USER_QUANTIZATIONS${TAUBENCH_USER_TEMPERATURE_MODE:-}" ]; then
    [[ "$TAUBENCH_USER_MODEL" == openrouter/* ]] && [ -z "${TAUBENCH_USER_BASE_URL:-}" ] || bad 'user provider/effort/quantizations requires openrouter/ model without TAUBENCH_USER_BASE_URL'
  fi
}

track_dry_run() {
  printf 'SESSION=%s\n' "$SESSION"
  printf 'COMMAND=env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL=%s TAUBENCH_TRIALS=%s AGENT_REQUEST_TIMEOUT=%s TAUBENCH_MAX_CONCURRENCY=%s' "$TAUBENCH_USER_MODEL" "$TAUBENCH_TRIALS" "$AGENT_REQUEST_TIMEOUT" "$TAUBENCH_MAX_CONCURRENCY"
  [ -z "$TAUBENCH_USER_PROVIDER" ] || printf ' TAUBENCH_USER_PROVIDER=%s' "$TAUBENCH_USER_PROVIDER"
  [ -z "$TAUBENCH_USER_QUANTIZATIONS" ] || printf ' TAUBENCH_USER_QUANTIZATIONS=%s' "$TAUBENCH_USER_QUANTIZATIONS"
  [ -z "$TAUBENCH_USER_REASONING_EFFORT" ] || printf ' TAUBENCH_USER_REASONING_EFFORT=%s' "$TAUBENCH_USER_REASONING_EFFORT"
  [ -z "${TAUBENCH_USER_TEMPERATURE_MODE:-}" ] || printf ' TAUBENCH_USER_TEMPERATURE_MODE=%s' "$TAUBENCH_USER_TEMPERATURE_MODE"
  printf ' bash vsm/taubench/run_taubench.sh %s %s\n' "$MODEL" "$BASE_URL_CHAT"
}

track_run() {
  local user_env=()
  [ -z "$TAUBENCH_USER_PROVIDER" ] || user_env+=("TAUBENCH_USER_PROVIDER=$TAUBENCH_USER_PROVIDER")
  [ -z "$TAUBENCH_USER_QUANTIZATIONS" ] || user_env+=("TAUBENCH_USER_QUANTIZATIONS=$TAUBENCH_USER_QUANTIZATIONS")
  [ -z "$TAUBENCH_USER_REASONING_EFFORT" ] || user_env+=("TAUBENCH_USER_REASONING_EFFORT=$TAUBENCH_USER_REASONING_EFFORT")
  [ -z "${TAUBENCH_USER_TEMPERATURE_MODE:-}" ] || user_env+=("TAUBENCH_USER_TEMPERATURE_MODE=$TAUBENCH_USER_TEMPERATURE_MODE")
  TS=$SESSION
  log "=== $LABEL 시작 MODEL=$MODEL host=$HOST session=$TS ==="
  mkdir -p "$BASE/logs/$TS"
  log "[$TS] taubench_std4 시작: TAUBENCH_MODE=standard TRIALS=$TAUBENCH_TRIALS 동시 $TAUBENCH_MAX_CONCURRENCY 사용자 ${TAUBENCH_USER_MODEL##*/}"
  ( EVAL_TIMESTAMP="$TS" env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL="$TAUBENCH_USER_MODEL" \
      TAUBENCH_TRIALS="$TAUBENCH_TRIALS" AGENT_REQUEST_TIMEOUT="$AGENT_REQUEST_TIMEOUT" TAUBENCH_MAX_CONCURRENCY="$TAUBENCH_MAX_CONCURRENCY" \
      ${user_env[@]+"${user_env[@]}"} bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT" ) 9>&- >>"$BASE/logs/$TS/taubench_std4.log" 2>&1
  rc=$?
  log "[$TS] taubench_std4 종료 rc=$rc"
  log "=== $END_LABEL 레인 종료 ==="
  # The lane exit status is the taubench runner status (unchanged from the old common tail).
  exit "$rc"
}
