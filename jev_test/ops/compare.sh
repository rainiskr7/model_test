#!/bin/bash
# 무엇: 동일 run의 일곱 판 비교. 입력: run_id model_id... 출력: compare.json·종료 코드.
source "$(dirname "$0")/lib.sh"
source ops/locks.sh
[ "$#" -ge 3 ] || { echo 'usage: compare.sh run_id model_id model_id ...'; exit 2; }
RID=$1; shift; M=compare
identifier "$RID" || exit 2
models=("$@")
seen=" "
for model in "${models[@]}"; do
  identifier "$model" || exit 2
  case "$seen" in *" $model "*) exit 2;; esac
  seen="$seen$model "
done
acquire_lock || exit $?
variants="klue_mrc_answerable/default korfin_asc/default fc_call_decision/default kmhas/default kote_escalation/default kosgd/full kosgd/actions_only"
# Check every existing destination before writing any comparison.
for sv in $variants; do
  cid="${RID}_${sv//\//_}"
  if dry; then
    show check-compare-models "$R/_compare/$cid/A/$sv/compare.json" "${models[@]}"
  else
    helper metadata compare "$R/_compare/$cid/A/$sv/compare.json" "${models[@]}" || exit $?
  fi
done
for sv in $variants; do
  dirs=()
  for model in "${models[@]}"; do dirs+=("$R/$model/$RID/A/$sv"); done
  step local compare --run-dirs "${dirs[@]}" --compare-id "${RID}_${sv//\//_}" --results "$R" || exit $?
done
