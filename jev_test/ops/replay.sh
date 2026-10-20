#!/bin/bash
# 무엇: 새 run에 출처 복사 후 재판정. 입력: model old_run new_run reason. 출력: replay·offline 기록.
source "$(dirname "$0")/lib.sh"
source ops/locks.sh
[ "$#" = 4 ] && [ -n "$4" ] || { echo 'usage: replay.sh model old_run new_run reason'; exit 2; }
M=$1 OLD=$2 RID=$3 REASON=$4 MY=configs/models/$1.yaml
identifier "$M" && identifier "$OLD" && identifier "$RID" && check_sets || exit 2
[ "$OLD" != "$RID" ] || exit 2
read_model || exit $?
acquire_lock || exit $?
copy_stage() {
  step local replay --model "$MY" --task "configs/tasks/$1.yaml" --stage "$2" --run-id "$RID" \
    --source-run-dir "$R/$M/$OLD/A/$(set_of "$1")/$(variant_of "$1")" --results "$R" --reason "$REASON"
}
offline() { step local run --model "$MY" --task "configs/tasks/$1.yaml" --stage "$2" --run-id "$RID" --results "$R" --offline; }
complete() {
  if dry; then return 0; fi
  local n
  n=$(printf '%s' "$LAST" | helper metadata deferred) || return $?
  if [ "$n" != 0 ]; then log "미수신 $n — 미복사 단계 확인 후 run으로 이어 전송 (ops/README.md)"; return 3; fi
}
stage() { copy_stage "$1" "$2" && offline "$1" "$2" && complete; }
actions_stage() {
  if derived_task kosgd_actions_only; then
    offline kosgd_actions_only "$1"
  else
    stage kosgd_actions_only "$1"
  fi
}
one_set() {
  stage "$1" dev && step local threshold --run-dir "$(dir_of "$1")" && stage "$1" test || return $?
  if [ "$1" = fc_call_decision ]; then stage "$1" extra || return $?; fi
  finish "$1"
}
kosgd() {
  stage kosgd_full dev && actions_stage dev &&
    step local threshold --run-dir "$(dir_of kosgd_full)" &&
    step local threshold --run-dir "$(dir_of kosgd_actions_only)" &&
    stage kosgd_full test && actions_stage test &&
    finish kosgd_full && finish kosgd_actions_only
}
rc=0
for S in ${SETS:-$DEFAULT_SETS}; do
  if [ -e "$W/STOP" ] || [ -e "$W/STOP.$M" ]; then exit 4; fi
  if [ "$S" = kosgd ]; then kosgd; else one_set "$S"; fi
  code=$?
  if [ "$code" != 0 ]; then rc=$code; log "셋 $S 중단 ($code)"; fi
done
exit "$rc"
