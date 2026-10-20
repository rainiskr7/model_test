#!/bin/bash
# 무엇: 단일 lane 소유·정리. 입력: 모델/run과 현재 PID. 출력: 잠금 디렉터리·종료 코드.
# lib.sh를 source한 뒤 사용한다. PID 재사용을 구별하려고 프로세스 시작 시각도 대조한다.
LOCK= LOCK_TOKEN=
process_token() {
  local state
  state=$(ps -p "$1" -o stat= 2>/dev/null) || return $?
  case "$state" in *Z*) return 1;; esac
  ps -p "$1" -o lstart= 2>/dev/null
}
release_lock() {
  clean_children
  if [ -n "$LOCK" ] && [ "$(cat "$LOCK/owner" 2>/dev/null)" = "$LOCK_TOKEN" ]; then
    rm -f "$LOCK/owner"
    rmdir "$LOCK" 2>/dev/null || :
  fi
}
acquire_lock() {
  dry && return 0
  mkdir -p "$W" || return 2
  LOCK="$W/lock.$M.$RID"
  local own_start
  own_start=$(process_token "$$") || { log "프로세스 소유 조회 실패"; LOCK=; return 2; }
  [ -n "$own_start" ] || { log "프로세스 시작 시각 없음"; LOCK=; return 2; }
  LOCK_TOKEN="$$|$own_start"
  if ! mkdir "$LOCK" 2>/dev/null; then
    local owner pid token current
    owner=$(cat "$LOCK/owner" 2>/dev/null) || { log "소유 정보 없는 잠금 — 수동 확인 필요"; LOCK=; return 2; }
    pid=${owner%%|*}; token=${owner#*|}
    [[ "$pid" =~ ^[0-9]+$ ]] && [ "$pid" -gt 1 ] && [ -n "$token" ] ||
      { log "손상된 잠금 — 수동 확인 필요"; LOCK=; return 2; }
    current=$(process_token "$pid")
    if [ -n "$current" ] || kill -0 "$pid" 2>/dev/null; then
      log "잠금 PID가 살아 있음 — 중복 실행 또는 PID 재사용 확인 필요"
      LOCK=; return 2
    fi
    # A reclaim directory serializes stale-lock recovery without deleting another owner.
    mkdir "$LOCK/reclaim" 2>/dev/null || { LOCK=; return 2; }
    if [ "$(cat "$LOCK/owner" 2>/dev/null)" != "$owner" ] || kill -0 "$pid" 2>/dev/null; then
      rmdir "$LOCK/reclaim"; LOCK=; return 2
    fi
    printf '%s\n' "$LOCK_TOKEN" > "$LOCK/owner"
    rmdir "$LOCK/reclaim"
  else
    printf '%s\n' "$LOCK_TOKEN" > "$LOCK/owner"
  fi
  trap release_lock EXIT
  trap 'exit 143' TERM
  trap 'exit 130' INT
}
