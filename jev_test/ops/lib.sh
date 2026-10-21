#!/bin/bash
# 무엇: 운영 명령 공통 실행. 입력: lane 인자·JEV_* 환경. 출력: CLI JSON·운영 로그. 계약 §9c.
set -u
OPS_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || exit 2
cd "$OPS_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
PY=${JEV_PY:-../foundation_model_test_non_thinking/.venv/bin/python}
W=$OPS_ROOT/.work/ops
R=results
BOOT='import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_module("jeveval.run.cli", run_name="__main__")'
HELPER='import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_path(sys.argv.pop(1), run_name="__main__")'
DEFAULT_SETS="klue_mrc_answerable korfin_asc fc_call_decision kmhas kote_escalation kosgd"
OPTIONAL_SETS="kosgd2"
CHILD= WATCH_PID= LAST=

dry() { [ "${OPS_DRY_RUN:-0}" = 1 ]; }
log() { printf '%s [%s] %s\n' "$(date '+%m-%d %H:%M:%S')" "${M:-ops}" "$*"; }
show() { printf 'DRY'; printf ' %q' "$@"; printf '\n'; }
identifier() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; }
helper() { "$PY" -I -B -c "$HELPER" "ops/$1.py" "${@:2}"; }
set_of() { case "$1" in kosgd2_*) echo kosgd2;; kosgd_*) echo kosgd;; *) echo "$1";; esac; }
variant_of() { case "$1" in kosgd_full|kosgd2_full) echo full;; kosgd_actions_only|kosgd2_actions_only) echo actions_only;; *) echo default;; esac; }
dir_of() { echo "$R/$M/$RID/A/$(set_of "$1")/$(variant_of "$1")"; }
check_sets() {
  for S in ${SETS:-$DEFAULT_SETS}; do
    case " $DEFAULT_SETS $OPTIONAL_SETS " in *" $S "*) ;; *) log "지원하지 않는 셋"; return 2;; esac
  done
}
url() {
  local ip=
  if ! dry; then
    ip=$(dscacheutil -q host -a name "${HOST%.local}.local" 2>/dev/null | awk '/ip_address/{print $2; exit}')
  fi
  printf 'http://%s:%s\n' "${ip:-$FALLBACK}" "$PORT"
}
read_model() {
  local meta
  meta=$(helper metadata model "$MY") || return $?
  IFS=$'\t' read -r KIND SERVED AUTH QUESTION_SCORING <<< "$meta"
}
derived_task() { [[ "$1" = kosgd_actions_only || "$1" = kosgd2_actions_only ]] && [ "$QUESTION_SCORING" = separate ]; }
load_model() {
  read_model || return $?
  [ "$AUTH" = "$KEYVAR" ] || { log "key_var와 모델 auth_env 불일치"; return 2; }
  [[ "$KEYVAR" =~ ^[A-Z_][A-Z0-9_]*$ ]] || return 2
  if dry; then return 0; fi
  if [ -z "${!KEYVAR:-}" ]; then
    local secret
    secret=$(helper metadata env "${JEV_ENV_FILE:-../foundation_model_test_non_thinking/.env}" "$KEYVAR") || return $?
    export "$KEYVAR=$secret"
  fi
}
healthy() {
  if dry; then
    if [ "$KIND" = systemone ]; then
      show healthy "$MY" "$(url)" 'systemone: GET /v1/models'
    else
      show healthy "$MY" "$(url)" 'b1: POST /v1/chat/completions (ping, 1 token)'
    fi
    return 0
  fi
  if [ "$KIND" = systemone ]; then
    # pipefail preserves curl failure even if a proxy returns a plausible JSON body.
    (set -o pipefail; curl -fsS -m 30 -H "Authorization: Bearer ${!KEYVAR}" "$(url)/v1/models" 2>/dev/null |
      helper metadata served "$SERVED")
  else
    local body code
    body=$(helper metadata ping "$SERVED") || return $?
    code=$(curl -s -m 60 -o /dev/null -w '%{http_code}' \
      -H "Authorization: Bearer ${!KEYVAR}" -H 'Content-Type: application/json' \
      "$(url)/v1/chat/completions" -d "$body") || return $?
    [ "$code" = 200 ]
  fi
}
wait_healthy() {
  local limit=${1:-43200} start=$SECONDS
  while ! healthy; do
    [ $((SECONDS - start)) -ge "$limit" ] && { log "건강 확인 상한 초과"; return 1; }
    log "서버 응답 없음 — 60초 후 확인"
    sleep 60
  done
}
clean_children() {
  if [ -n "$WATCH_PID" ]; then kill -TERM "$WATCH_PID" 2>/dev/null || :; wait "$WATCH_PID" 2>/dev/null || :; WATCH_PID=; fi
  if [ -n "$CHILD" ]; then kill -TERM "$CHILD" 2>/dev/null || :; wait "$CHILD" 2>/dev/null || :; CHILD=; fi
}
step() {
  local kind=$1; shift
  local tries=0 rc
  local args=("$@")
  if dry; then
    [ "$kind" != run ] || healthy
    if [ "$kind" = run ]; then args+=(--base-url "$(url)"); fi
    show "$PY" -I -B -c "$BOOT" "${args[@]}"
    LAST='{"ok":true,"n_deferred":0}'
    return 0
  fi
  while :; do
    local invocation=("${args[@]}")
    if [ "$kind" = run ]; then
      wait_healthy "${JEV_WAIT_SECONDS:-43200}" || return $?
      invocation+=(--base-url "$(url)")
    fi
    "$PY" -I -B -c "$BOOT" "${invocation[@]}" > "$W/$M.$RID.last.out" 2>&1 & CHILD=$!
    if [ "$kind" = run ]; then
      "$PY" -I -B ops/watch.py "$ATT" "$CHILD" >> "$W/$M.$RID.watch.log" 2>&1 & WATCH_PID=$!
    fi
    wait "$CHILD"; rc=$?; CHILD=
    clean_children
    LAST=$(tail -n 1 "$W/$M.$RID.last.out")
    log "$LAST"; log "exit=$rc"
    [ "$rc" != 0 ] || return 0
    [ "$kind" = run ] || return "$rc"
    tries=$((tries + 1))
    [ "$tries" -lt 3 ] || return "$rc"
    log "run 실패 — 다시 시도 ($tries/3)"
    sleep 30
  done
}
run_stage() {
  local task=$1 stage=$2 kind=run
  local args=(run --model "$MY" --task "configs/tasks/$task.yaml" --stage "$stage" --run-id "$RID" --results "$R")
  ATT="$(dir_of "$task")/$stage/attempts.jsonl"
  if derived_task "$task"; then kind=local; args+=(--offline); fi
  step "$kind" "${args[@]}"
}
threshold() {
  if [ -e "$1/test/seal.json" ]; then log "threshold 생략: 봉인 존재 $1"; return 0; fi
  step local threshold --run-dir "$1"
}
finish() { step local score --run-dir "$(dir_of "$1")" && step local certify --run-dir "$(dir_of "$1")"; }
