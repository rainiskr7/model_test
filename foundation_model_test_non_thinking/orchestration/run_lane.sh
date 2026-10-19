#!/bin/bash
# Invoke as lanes/<track>.sh <model_conf>; do not resolve the entry symlink.
set -u
bad() { printf 'run_lane: %s\n' "$*" >&2; exit 2; }
[ "$#" -eq 1 ] || bad 'expected one model_conf argument'
model_conf=$1
[[ "$model_conf" =~ ^[a-z0-9_]+$ ]] || bad 'invalid model_conf: use [a-z0-9_] only'
TRACK=$(basename "$0" .sh)
case "$TRACK" in kmmlu|taubench_std4|full) ;; *) bad "unknown TRACK: $TRACK" ;; esac
lane=${model_conf}_${TRACK}
HERE=$(cd "$(dirname "$0")/.." && pwd) || exit 2
BASE=$(cd "$HERE/.." && pwd) || exit 2
conf=$HERE/models/$model_conf.conf
CONFIG= HOST_ENV= HOST_DEFAULT= KEYVAR= DISPLAY= LANE_TOKENIZER=
SESSION_KMMLU= SESSION_TAUBENCH_STD4= SESSION_FULL=
REPS=3 REQUIRE_NOTHINK=1 LM_EVAL_MODE=chat NUM_CONCURRENT=8
TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini
TAUBENCH_TRIALS=4 TAUBENCH_MAX_CONCURRENCY=4 AGENT_REQUEST_TIMEOUT=300
FULL_KRETA_WORKERS=4 FULL_KRETA_RESUME=0 FULL_RESUME_FROM=
FULL_AGENT_TASK_TIMEOUT=900
# A whitelist maps literal conf keys to variables; no shell evaluation.
config_setting() {
  local setting=$1 value=$2 scope=$3 pass=$4 variable
  case "$setting" in
    CONFIG|HOST_ENV|HOST_DEFAULT|KEYVAR|DISPLAY|SESSION_KMMLU|SESSION_TAUBENCH_STD4|SESSION_FULL)
      [ "$scope" = common ] || bad "key cannot have track prefix: $setting"
      variable=$setting ;;
    REPS|LANE_TOKENIZER|REQUIRE_NOTHINK|LM_EVAL_MODE|NUM_CONCURRENT|TAUBENCH_USER_MODEL|TAUBENCH_TRIALS|TAUBENCH_MAX_CONCURRENCY|AGENT_REQUEST_TIMEOUT)
      variable=$setting ;;
    AGENT_TASK_TIMEOUT|KRETA_WORKERS|KRETA_RESUME|RESUME_FROM) variable=FULL_$setting ;;
    *) bad "unknown key: $setting" ;;
  esac
  [ "$scope" != "$pass" ] || printf -v "$variable" '%s' "$value"
}

read_config() {
  local pass=$1 line key value scope
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue ;; *=*) ;; *) bad "expected key=value: $line" ;; esac
    key=${line%%=*}; value=${line#*=}; scope=common
    # Optional enclosing quotes are literal delimiters, never shell evaluation.
    case "$value" in \"*\") value=${value#\"}; value=${value%\"} ;; \'*\') value=${value#\'}; value=${value%\'} ;; esac
    case "$key" in
      KMMLU_*) scope=kmmlu; key=${key#KMMLU_} ;;
      TAUBENCH_STD4_*) scope=taubench_std4; key=${key#TAUBENCH_STD4_} ;;
      FULL_*) scope=full; key=${key#FULL_} ;;
    esac
    config_setting "$key" "$value" "$scope" "$pass"
  done < "$conf"
}
[ -f "$conf" ] || bad "missing conf: $conf"
read_config common
read_config "$TRACK"
for key in CONFIG HOST_ENV HOST_DEFAULT KEYVAR DISPLAY; do
  [ -n "${!key}" ] || bad "required key: $key"
done
case "$TRACK" in
  kmmlu) session_key=SESSION_KMMLU ;;
  taubench_std4) session_key=SESSION_TAUBENCH_STD4 ;;
  full) session_key=SESSION_FULL ;;
esac
SESSION=${!session_key}
[ -n "$SESSION" ] || bad "required key: $session_key"
LABEL="$DISPLAY $TRACK" PREFIX="$DISPLAY $TRACK"
STOP_LABEL="$DISPLAY $TRACK" END_LABEL="$DISPLAY $TRACK"
case "$HOST_ENV:$KEYVAR" in *[!a-zA-Z0-9_:]*|[0-9]*|*:[0-9]*) bad 'invalid environment variable name' ;; esac
source "$HERE/tracks/$TRACK.sh"
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
# The template check remains after the HOST lock and before HTTP preflight.
if [ "$TRACK" = kmmlu ] && [ "$REQUIRE_NOTHINK" = 1 ]; then
  grep -q 'set enable_thinking = false' "$TOK/chat_template.jinja" || { log "$PREFIX: 생각 끈 사본이 아니다 — $TOK"; exit 1; }
fi
body="$(mktemp)"; code="$(curl -s -m 10 -o "$body" -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models")"
if [ "$code" != 200 ] || ! grep -q "\"id\":\"$MODEL\"" "$body"; then log "$PREFIX: preflight 실패 HTTP $code"; rm -f "$body"; exit 1; fi; rm -f "$body"
track_run
