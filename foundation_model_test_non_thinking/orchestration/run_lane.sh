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
    *) bad "unknown key: $key" ;;
  esac
done < "$conf"
for key in CONFIG HOST_ENV HOST_DEFAULT KEYVAR TRACK SESSION LABEL PREFIX END_LABEL; do
  [ -n "${!key}" ] || bad "required key: $key"
done
case "$HOST_ENV:$KEYVAR" in *[!a-zA-Z0-9_:]*|[0-9]*|*:[0-9]*) bad 'invalid environment variable name' ;; esac
case "$TRACK" in
  kmmlu)
    [ -n "$LANE_TOKENIZER" ] || bad 'required key: LANE_TOKENIZER'
    [ -n "$STOP_LABEL" ] || bad 'required key: STOP_LABEL'
    case "$REPS" in ''|*[!0-9]*) bad 'REPS must be positive' ;; esac
    [ "$REPS" -gt 0 ] || bad 'REPS must be positive'
    case "$NUM_CONCURRENT" in [1-8]) ;; *) bad 'NUM_CONCURRENT must be 1..8' ;; esac
    case "$REQUIRE_NOTHINK" in 0|1) ;; *) bad 'REQUIRE_NOTHINK must be 0 or 1' ;; esac
    ;;
  taubench_std4) ;;
  *) bad "unknown TRACK: $TRACK" ;;
esac
cd "$BASE" || exit 1
source "$BASE/.venv/bin/activate"
export MODEL_TEST_BASE="$BASE"
if [ "$TRACK" = kmmlu ]; then export NUM_CONCURRENT LM_EVAL_MODE
else export TAUBENCH_MAX_CONCURRENCY; fi
ORCH="$BASE/logs/resume_orch"
HOST=${!HOST_ENV:-$HOST_DEFAULT}
TOK=$LANE_TOKENIZER
BASE_TS=$SESSION
read_key() { grep -E "^$1=" "$BASE/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }
# Dry-run never opens .env, writes logs, or performs preflight.
if [ "${LANE_DRY_RUN:-0}" != 1 ]; then
  export OPENAI_API_KEY="$(read_key "$KEYVAR")"
  if [ "$TRACK" = taubench_std4 ]; then export TAUBENCH_USER_API_KEY="$(read_key TAUBENCH_USER_API_KEY)"; fi
fi
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$ORCH/orchestrator.log"; }
export BASE_URL_CHAT_OVERRIDE=http://$HOST/v1/chat/completions
export BASE_URL_V1_OVERRIDE=http://$HOST/v1
loader=$(python "$BASE/configs/load_model_config.py" "$CONFIG" 2>/dev/null) || exit 1
eval "$loader"
if [ "${LANE_DRY_RUN:-0}" = 1 ]; then
  printf 'BASE=%s\nconf=%s\nHOST=%s\n' "$BASE" "$conf" "$HOST"
  if [ "$TRACK" = kmmlu ]; then
    N=1
    while [ "$N" -le "$REPS" ]; do printf 'SESSION=%s_r%s\n' "$SESSION" "$N"; N=$((N + 1)); done
    printf 'COMMAND=bash vsm/harness/run_harness.sh %s %s %s\n' "$MODEL" "$TOK" "$BASE_URL_CHAT"
  else
    printf 'SESSION=%s\n' "$SESSION"
    printf 'COMMAND=env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL=%s TAUBENCH_TRIALS=%s AGENT_REQUEST_TIMEOUT=%s TAUBENCH_MAX_CONCURRENCY=%s bash vsm/taubench/run_taubench.sh %s %s\n' "$TAUBENCH_USER_MODEL" "$TAUBENCH_TRIALS" "$AGENT_REQUEST_TIMEOUT" "$TAUBENCH_MAX_CONCURRENCY" "$MODEL" "$BASE_URL_CHAT"
  fi
  exit 0
fi
# Preserve the exact wording supplied by each lane's configuration.
if [ "$TRACK" = kmmlu ] && [ "$REQUIRE_NOTHINK" = 1 ]; then
  grep -q 'set enable_thinking = false' "$TOK/chat_template.jinja" || { log "$PREFIX: 생각 끈 사본이 아니다 — $TOK"; exit 1; }
fi
body="$(mktemp)"; code="$(curl -s -m 10 -o "$body" -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models")"
if [ "$code" != 200 ] || ! grep -q "\"id\":\"$MODEL\"" "$body"; then log "$PREFIX: preflight 실패 HTTP $code"; rm -f "$body"; exit 1; fi; rm -f "$body"
if [ "$TRACK" = kmmlu ]; then
  log "=== $LABEL 시작 MODEL=$MODEL host=$HOST tok=$TOK sessions=${BASE_TS}_r1..r$REPS ==="
  N=1
  while [ "$N" -le "$REPS" ]; do
    TS="${BASE_TS}_r${N}"
    mkdir -p "$BASE/logs/$TS"
    log "[$TS] harness 시작: run_harness.sh $MODEL $TOK $BASE_URL_CHAT (LM_EVAL_MODE=$LM_EVAL_MODE)"
    ( EVAL_TIMESTAMP="$TS" bash vsm/harness/run_harness.sh "$MODEL" "$TOK" "$BASE_URL_CHAT" ) >>"$BASE/logs/$TS/harness_${MODEL}.log" 2>&1
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
      bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT" ) >>"$BASE/logs/$TS/taubench_std4.log" 2>&1
  rc=$?
  log "[$TS] taubench_std4 종료 rc=$rc"
fi
log "=== $END_LABEL 레인 종료 ==="
[ "$TRACK" != taubench_std4 ] || exit "$rc"
