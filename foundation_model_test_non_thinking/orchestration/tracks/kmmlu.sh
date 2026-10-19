# Sourced by run_lane.sh; definitions only, using the common lane context.
# Inputs (phases: README.md): LANE_TOKENIZER STOP_LABEL REPS NUM_CONCURRENT
# REQUIRE_NOTHINK LM_EVAL_MODE SESSION MODEL TOK BASE_URL_CHAT LABEL HOST BASE_TS
# BASE END_LABEL PREFIX; functions: bad log.
track_export() { export NUM_CONCURRENT LM_EVAL_MODE; }

track_pre_http() {
  if [ "$REQUIRE_NOTHINK" = 1 ]; then
    grep -q 'set enable_thinking = false' "$TOK/chat_template.jinja" || {
      log "$PREFIX: 생각 끈 사본이 아니다 — $TOK"
      return 1
    }
  fi
  return 0
}

track_validate() {
  [ -n "$LANE_TOKENIZER" ] || bad 'required key: LANE_TOKENIZER'
  [ -n "$STOP_LABEL" ] || bad 'required key: STOP_LABEL'
  case "$REPS" in ''|*[!0-9]*) bad 'REPS must be positive' ;; esac
  [ "$REPS" -gt 0 ] || bad 'REPS must be positive'
  case "$NUM_CONCURRENT" in [1-8]) ;; *) bad 'NUM_CONCURRENT must be 1..8' ;; esac
  case "$REQUIRE_NOTHINK" in 0|1) ;; *) bad 'REQUIRE_NOTHINK must be 0 or 1' ;; esac
}

track_dry_run() {
  N=1
  while [ "$N" -le "$REPS" ]; do printf 'SESSION=%s_r%s\n' "$SESSION" "$N"; N=$((N + 1)); done
  printf 'COMMAND=bash vsm/harness/run_harness.sh %s %s %s\n' "$MODEL" "$TOK" "$BASE_URL_CHAT"
}

track_run() {
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
  log "=== $END_LABEL 레인 종료 ==="
  return 0
}
