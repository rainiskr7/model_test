#!/bin/bash
# Unified server/temperature guard. Start in its own process group:
# perl -e 'setpgrp; exec @ARGV' bash /absolute/orchestration/lane_guard.sh
# The old watchdog/temp_guard must already have been retired by the operator.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LANES_LOGICAL=$HERE/lanes
LANES_PHYSICAL=$(cd "$LANES_LOGICAL" && pwd -P) || exit 4
# Escape literal paths for pgrep's extended regular expression. Keep the lane
# symlink basename: resolving the script itself would collapse all lane names.
ere_literal() { printf '%s' "$1" | sed 's/[][\\.^$*+?(){}|]/\\&/g'; }
lane_pattern() {
  local logical physical
  logical=$(ere_literal "$LANES_LOGICAL/$1.sh")
  physical=$(ere_literal "$LANES_PHYSICAL/$1.sh")
  if [ "$logical" = "$physical" ]; then printf '%s' "$logical"
  else printf '(%s|%s)' "$logical" "$physical"; fi
}
BASE=$HERE/..
ORCH=${LANEGUARD_RUNTIME_DIR:-$BASE/logs/resume_orch}
mkdir -p "$ORCH" || exit 4
source "$BASE/shared/harness/harness_lib.sh" || exit 4
STATE="${LANEGUARD_STATE_DIR:-$ORCH/.lane_guard}"
LOG="${LANEGUARD_LOG:-$ORCH/orchestrator.log}"
INTERVAL="${LANEGUARD_INTERVAL:-10}"
mkdir -p "$STATE" || exit 4
harness_lock "$ORCH/.lane_guard.lock" || exit $?
# Fail closed if process inspection is unavailable (including sandbox denial).
ps -p $$ -o pid= >/dev/null 2>&1 || { echo '[lane_guard] process inspection unavailable' >&2; exit 4; }
LANES="${LANEGUARD_LANES-$(grep -v '^[[:space:]]*#' "$HERE/lanes.conf" | grep -v '^[[:space:]]*$')}"
log() { printf '[%s] [lane_guard] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
resolve() { dscacheutil -q host -a name "$1.local" 2>/dev/null | awk '/ip_address/{print $2; exit}'; }
health() {
  if [ -n "${LANEGUARD_HEALTH_CMD:-}" ]; then "$LANEGUARD_HEALTH_CMD" "$name" "$hostname" "$model" 9>&-; return $?; fi
  # 옛 lane_watchdog.sh:27–35 와 같은 판정: 모델 목록(10초)에 모델이 있고, 1토큰 요청(60초)이 200.
  local host key code body
  host=$(resolve "$hostname"); [ -n "$host" ] || return 1
  key=$(sed -n "s/^${keyvar}=//p" "$BASE/.env" | head -1 | tr -d '\"'"'"' ')
  body=$(mktemp "$STATE/.health.XXXXXX") || return 1
  code=$(curl -s -m 10 -o "$body" -w '%{http_code}' -H "Authorization: Bearer $key" "http://$host:18023/v1/models" 9>&-)
  if [ "$code" != 200 ] || ! grep -q "\"id\":\"$model\"" "$body"; then rm -f "$body"; return 1; fi
  rm -f "$body"
  code=$(curl -s -m 60 -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"1\"}],\"max_tokens\":1}" \
    "http://$host:18023/v1/chat/completions" 9>&-)
  [ "$code" = 200 ]
}
temperatures() {
  if [ -n "${LANEGUARD_TEMP_CMD:-}" ]; then "$LANEGUARD_TEMP_CMD" "$name" "$hostname" 9>&-; return $?; fi
  local host gpu sensor
  host=$(resolve "$hostname"); [ -n "$host" ] || return 1
  gpu=$(curl -s -m 5 "http://$host:9400/metrics" 9>&- | awk '/^DCGM_FI_DEV_GPU_TEMP/{print int($NF); exit}')
  sensor=$(curl -s -m 8 "http://$host:9100/metrics" 9>&- | awk '/^node_hwmon_temp_celsius\{chip="thermal/{v=$NF+0;if(v>m)m=v;n++}END{if(n)print int(m)}')
  # 센서를 못 읽으면 GPU 로만 판단한다(옛 temp_guard.sh:40 과 같음). 둘 다 요구하면 센서 고장 때 과열 정지가 영영 안 걸린다.
  [ -n "$gpu" ] || return 1
  printf '%s %s\n' "$gpu" "${sensor:-0}"
}
identity() { LC_ALL=C ps -p "$1" -o lstart= 2>/dev/null | sed 's/^ *//;s/ *$//'; }
status() { ps -p "$1" -o stat= 2>/dev/null; }
# One atomic snapshot per lane, including reasons, counters and process ownership.
# Ownership record: pid|C-locale lstart|pending/held/ambiguous
# Manual-stop warning records are separate and never grant CONT ownership.
save_state() {
  local temp p stamp
  temp=$(mktemp "$STATE/.${name}.XXXXXX") || exit 4
  {
    printf 'state|%s|%s|%s|%s|%s|%s\n' "$instance" "$server" "$heat" "$fails" "$oks" "$cool"
    printf 'warnings|%s|%s|%s\n' "$duplicate_warned" "$unsupported_warned" "$temp_warned"
    [ -z "$entries" ] || printf '%s\n' "$entries"
    while IFS='|' read -r p stamp; do
      [ -z "$p" ] || printf 'observed|%s|%s\n' "$p" "$stamp"
    done <<< "$manual_seen"
  } > "$temp"
  mv "$temp" "$STATE/$name.state" || { rm -f "$temp"; exit 4; }
}
load_state() {
  instance="" server=0 heat=0 fails=0 oks=0 cool=0 entries="" manual_seen=""
  duplicate_warned=0 unsupported_warned=0 temp_warned=0
  local kind a b c d e f
  [ -f "$STATE/$name.state" ] || return 0
  while IFS='|' read -r kind a b c d e f; do
    case "$kind" in
      state) instance=$a; server=$b; heat=$c; fails=$d; oks=$e; cool=$f ;;
      warnings) duplicate_warned=$a; unsupported_warned=$b; temp_warned=${c:-0} ;;
      observed) manual_seen="${manual_seen}${manual_seen:+
}${a}|${b}" ;;
      ''|*[!0-9]*) ;;
      *) entries="${entries}${entries:+
}${kind}|${a}|${b}" ;;
    esac
  done < "$STATE/$name.state"
}
entry_set() {
  local pid="$1" stamp="$2" kind="$3" line p s k updated=""
  while IFS='|' read -r p s k; do
    [ -n "$p" ] || continue
    [ "$p" = "$pid" ] && continue
    updated="${updated}${updated:+
}${p}|${s}|${k}"
  done <<< "$entries"
  if [ -n "$kind" ]; then updated="${updated}${updated:+
}${pid}|${stamp}|${kind}"; fi
  entries=$updated
  save_state
}
entry_kind() {
  local p s k
  while IFS='|' read -r p s k; do
    if [ "$p" = "$1" ] && [ "$s" = "$2" ]; then printf '%s' "$k"; return; fi
  done <<< "$entries"
}
warn_manual() {
  local p stamp
  while IFS='|' read -r p stamp; do
    [ "$p" != "$1" ] || [ "$stamp" != "$2" ] || return 0
  done <<< "$manual_seen"
  log "$name: T 상태 발견 — 사람이 확인 pid=$1"
  manual_seen="${manual_seen}${manual_seen:+
}${1}|${2}"
  save_state
}
signal_one() {
  local sig="$1" p="$2" rc cmd
  kill -"$sig" "$p" 2>/dev/null; rc=$?
  cmd=$(ps -p "$p" -o command= 2>/dev/null | cut -c 1-120)
  log "$name: $sig pid=$p cmd=$cmd rc=$rc"
  return "$rc"
}
recover_entries() {
  local snapshot="$entries" p stamp kind now st
  while IFS='|' read -r p stamp kind; do
    [ -n "$p" ] || continue
    now=$(identity "$p")
    if [ -z "$now" ] || [ "$now" != "$stamp" ]; then entry_set "$p" "$stamp" ''; continue; fi
    st=$(status "$p")
    case "$kind:$st" in
      pending:*T*)
        log "$name: pending+T — 자기가 멈춘 것인지 불명, 사람이 확인 pid=$p"
        entry_set "$p" "$stamp" ambiguous ;;
      pending:*) entry_set "$p" "$stamp" '' ;;
      held:*T*|ambiguous:*T*) ;;
      *) entry_set "$p" "$stamp" '' ;;
    esac
  done <<< "$snapshot"
}
stop_tree() {
  local pass p stamp st kind
  for pass in 1 2; do
    for p in $(harness_descendants "$root"); do
      stamp=$(identity "$p"); [ -n "$stamp" ] || continue
      st=$(status "$p"); kind=$(entry_kind "$p" "$stamp")
      case "$st" in
        *T*)
          if [ -z "$kind" ]; then
            warn_manual "$p" "$stamp"
          fi
          continue ;;
      esac
      entry_set "$p" "$stamp" pending
      # Recheck identity immediately before each signal.
      if [ "$(identity "$p")" = "$stamp" ] && signal_one STOP "$p"; then
        entry_set "$p" "$stamp" held
      else
        entry_set "$p" "$stamp" ''
      fi
    done
  done
}
resume_entries() {
  local snapshot p stamp kind pass st
  # Reverse discovery order gives children before parents, root explicitly last.
  snapshot=$(printf '%s\n' "$entries" | awk '{a[NR]=$0}END{for(i=NR;i>0;i--)print a[i]}')
  for pass in children root; do
    while IFS='|' read -r p stamp kind; do
      [ -n "$p" ] && [ "$kind" = held ] || continue
      if [ "$pass" = children ]; then [ "$p" != "$root" ] || continue
      else [ "$p" = "$root" ] || continue; fi
      [ "$(identity "$p")" = "$stamp" ] || { entry_set "$p" "$stamp" ''; continue; }
      st=$(status "$p")
      case "$st" in
        *T*) signal_one CONT "$p" && entry_set "$p" "$stamp" '' ;;
        *) entry_set "$p" "$stamp" '' ;;
      esac
    done <<< "$snapshot"
  done
}
log "시작 PID=$$ interval=${INTERVAL}s"
first_cycle=1
while :; do
  while IFS= read -r lane_row; do
    [ -n "$lane_row" ] || continue
    if ! [[ "$lane_row" =~ ^[^\|]+\|[^\|]+\|[^\|]+\|[^\|]+\|[^\|]+\|[^\|]+$ ]]; then
      log 'invalid lane row: expected six nonempty fields'; exit 4
    fi
    IFS='|' read -r name track model_conf hostname keyvar model <<< "$lane_row"
    if ! [[ "$track" =~ ^[a-z0-9_]+$ ]] || [ ! -f "$HERE/tracks/$track.sh" ]; then
      log 'invalid lane track'; exit 4
    fi
    if ! [[ "$model_conf" =~ ^[a-z0-9_]+$ ]] || [ "$name" != "${model_conf}_${track}" ] ||
       [ -z "$hostname" ] || [ -z "$keyvar" ] || [ -z "$model" ]; then
      log 'invalid lane row: expected name|track|model_conf|hostname|keyvar|model'; exit 4
    fi
    load_state
    script_pattern=$(lane_pattern "$track")
    roots=$(pgrep -f "^([^ ]*/)?bash ${script_pattern} ${model_conf}$" 2>/dev/null)
    count=$(printf '%s\n' "$roots" | awk 'NF{n++}END{print n+0}')
    if [ "$count" -ge 2 ]; then
      if [ "$duplicate_warned" = 0 ]; then log "$name: 레인 2개 이상 — 신호 없음"; duplicate_warned=1; save_state; fi
      continue
    fi
    root=$roots
    if [ -z "$root" ] && [ "$unsupported_warned" = 0 ]; then
      # Warn for missing args or this model with options/extra args. A valid
      # invocation for a different model on the same track is not this lane.
      if ps -axo command= | grep -E "^([^ ]*/)?bash (.*[[:space:]])?${script_pattern}([[:space:]]*$|[[:space:]]+${model_conf}([[:space:]]|$))" >/dev/null; then
        log "$name: 미지원 실행 형태"; unsupported_warned=1
      fi
    fi
    new_instance=""
    [ -z "$root" ] || new_instance="$root:$(identity "$root")"
    if [ "$new_instance" != "$instance" ] || [ "$first_cycle" = 1 ]; then
      log "$name: 레인 식별 root=${root:-없음} instance=${new_instance:-없음}"
    fi
    if [ "$new_instance" != "$instance" ]; then
      instance=$new_instance; fails=0; oks=0; cool=0
      # 레인이 없던 동안의 사유 값을 새 레인에 물려주지 않는다(내가 멈춘 항목이 남아 있으면 유지).
      [ -n "$entries" ] || { server=0; heat=0; }
    fi
    recover_entries
    # No live root still needs health/heat updates for held orphan descendants.
    if [ -z "$root" ] && [ -z "$entries" ]; then save_state; continue; fi
    if health; then fails=0; oks=$((oks + 1)); [ "$oks" -lt 2 ] || server=0
    else oks=0; fails=$((fails + 1)); [ "$fails" -lt 2 ] || server=1; fi
    temp=$(temperatures) || temp=""
    if [ -z "$temp" ]; then
      cool=0
      [ "$temp_warned" = 1 ] || { log "$name: 온도 읽기 실패 — heat=$heat 유지, 회복 카운터 초기화"; temp_warned=1; }
    elif [ "$temp_warned" = 1 ]; then
      log "$name: 온도 읽기 회복"; temp_warned=0
    fi
    gpu="" sensor=""; read -r gpu sensor <<< "$temp"
    # 센서만 못 읽으면 GPU 로만 판단한다(옛 temp_guard.sh 와 같음) — 주입 명령 경로에도 똑같이 적용.
    [ -z "$gpu" ] || sensor=${sensor:-0}
    case "$gpu:$sensor" in *[!0-9:]*|:*|*:) ;; *)
      if [ "$gpu" -ge 84 ] || [ "$sensor" -ge 96 ]; then heat=1; cool=0
      elif [ "$gpu" -le 72 ] && [ "$sensor" -le 85 ]; then cool=$((cool + 1)); [ "$cool" -lt 3 ] || heat=0
      else cool=0; fi ;;
    esac
    save_state
    if [ "$server" = 1 ] || [ "$heat" = 1 ]; then
      [ -z "$root" ] || stop_tree
    else
      # Observe manually stopped processes even when no reason is active.
      for p in $(harness_descendants "$root"); do
        stamp=$(identity "$p"); [ -n "$stamp" ] || continue
        case "$(status "$p")" in *T*)
          if [ -z "$(entry_kind "$p" "$stamp")" ]; then
            warn_manual "$p" "$stamp"
          fi ;;
        esac
      done
      resume_entries
    fi
  done <<< "$LANES"
  first_cycle=0
  [ "${LANEGUARD_ONCE:-0}" != 1 ] || break
  sleep "$INTERVAL" 9>&-
done
