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
# Validate the name before selecting the track's function definitions.
case "$TRACK" in
  kmmlu|taubench_std4|full) source "$HERE/tracks/$TRACK.sh" ;;
  *) bad "unknown TRACK: $TRACK" ;;
esac
track_validate
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
  track_dry_run
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
track_run
