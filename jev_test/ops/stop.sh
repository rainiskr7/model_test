#!/bin/bash
# 무엇: 셋 경계 STOP 또는 소유 lane TERM. 입력: [now] [model_id]. 출력: STOP·종료 관측.
source "$(dirname "$0")/lib.sh"
source ops/locks.sh
mode=later
if [ "${1:-}" = now ]; then mode=now; shift; fi
[ "$#" -le 1 ] || exit 2
M=${1:-}
if [ -n "$M" ]; then identifier "$M" || exit 2; fi
marker="$W/STOP${M:+.$M}"
if dry; then show touch "$marker"; [ "$mode" != now ] || show TERM-owned-lanes "${M:-all}"; exit 0; fi
mkdir -p "$W" || exit 2
touch "$marker" || exit 2
[ "$mode" = now ] || { log "STOP 표시 — 셋 경계에서 중단"; exit 0; }
rc=0
for lock in "$W"/lock.*; do
  [ -d "$lock" ] || continue
  if [ -n "$M" ]; then case "${lock##*/}" in "lock.$M."*) ;; *) continue;; esac; fi
  owner=$(cat "$lock/owner" 2>/dev/null) || { rc=2; continue; }
  pid=${owner%%|*}; token=${owner#*|}
  [[ "$pid" =~ ^[0-9]+$ ]] && [ "$pid" -gt 1 ] && [ -n "$token" ] || { rc=2; continue; }
  current=$(process_token "$pid")
  if [ -z "$current" ]; then
    state=$(ps -p "$pid" -o stat= 2>/dev/null)
    case "$state" in *Z*) continue;; esac
    if kill -0 "$pid" 2>/dev/null; then log "살아 있는 PID 소유 조회 실패"; rc=2; fi
    continue
  fi
  if [ "$current" != "$token" ]; then log "PID 소유 불일치 — TERM 생략"; rc=2; continue; fi
  # Confirm the process is one of our entrypoints, not merely a reused PID.
  args=$(ps -p "$pid" -o args=)
  case "$args" in *ops/lane.sh*|*ops/replay.sh*|*ops/compare.sh*) ;; *) rc=2; continue;; esac
  kill -TERM "$pid" 2>/dev/null || rc=2
  for attempt in 1 2 3; do
    [ "$(process_token "$pid")" = "$token" ] || break
    sleep 1
  done
  if [ "$(process_token "$pid")" = "$token" ]; then log "프로세스가 아직 남음"; rc=1; fi
done
exit "$rc"
