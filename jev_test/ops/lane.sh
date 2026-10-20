#!/bin/bash
# 무엇: 새 본시험·같은 run 재개. 입력: model host fallback port key_var run_id. 출력: CLI 기록·로그.
source "$(dirname "$0")/lib.sh"
source ops/locks.sh
[ "$#" = 6 ] || { echo 'usage: lane.sh model host fallback port key_var run_id'; exit 2; }
M=$1 HOST=$2 FALLBACK=$3 PORT=$4 KEYVAR=$5 RID=$6 MY=configs/models/$1.yaml
identifier "$M" && identifier "$RID" && [[ "$PORT" =~ ^[0-9]+$ ]] && check_sets || exit 2
acquire_lock || exit $?
load_model || exit $?
one_set() {
  local task=$1
  run_stage "$task" dev && threshold "$(dir_of "$task")" && run_stage "$task" test || return $?
  if [ "$task" = fc_call_decision ]; then run_stage "$task" extra || return $?; fi
  finish "$task"
}
kosgd() {
  run_stage kosgd_full dev && run_stage kosgd_actions_only dev &&
    threshold "$(dir_of kosgd_full)" && threshold "$(dir_of kosgd_actions_only)" &&
    run_stage kosgd_full test && run_stage kosgd_actions_only test &&
    finish kosgd_full && finish kosgd_actions_only
}
rc=0
for S in ${SETS:-$DEFAULT_SETS}; do
  if [ -e "$W/STOP" ] || [ -e "$W/STOP.$M" ]; then log "STOP — 셋 경계에서 중단"; exit 4; fi
  if [ "$S" = kosgd ]; then kosgd; else one_set "$S"; fi
  code=$?
  if [ "$code" != 0 ]; then rc=$code; log "셋 $S 실패 ($code)"; fi
done
exit "$rc"
