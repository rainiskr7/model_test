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
# Parse before activation; these environment settings belong only to the CLI.
lane_settings=$(PYTHONPATH="$BASE" PYTHONDONTWRITEBYTECODE=1 "$BASE/.venv/bin/python" -B \
  -m orchestration.laneconf --tracks-dir "$HERE/tracks" "$conf" "$TRACK") || exit "$?"
eval "$lane_settings"
LABEL="$DISPLAY $TRACK" PREFIX="$DISPLAY $TRACK"
STOP_LABEL="$DISPLAY $TRACK" END_LABEL="$DISPLAY $TRACK"
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
