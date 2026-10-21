#!/bin/bash
# 무엇: kosgd2 순서 조립 · 입력: lane 환경 · 출력: 등록/실행 명령 · 계약 §7-4b·7-4d.
kosgd2_action() {
  local task=$1 phase=$2 action
  if dry; then echo create; return 0; fi
  action=$(helper registration_status "$(dir_of "$task")" "$phase") || return $?
  case "$action" in create|skip) printf '%s\n' "$action";; *) return 2;; esac
}
kosgd2_needed() {
  local task=$1 phase=$2 action
  shift 2
  action=$(kosgd2_action "$task" "$phase") || return $?
  [ "$action" != skip ] || { log "$task $phase 생략: 검증됨"; return 0; }
  "$@"
}
kosgd2_stage() {
  kosgd2_needed "$1" "$2" run_stage "$1" "$2"
}
kosgd2_threshold() {
  local command=("$2")
  [ "$2" != variant-threshold ] || command=(score-variants threshold)
  kosgd2_needed "$1" "$2" step local "${command[@]}" --run-dir "$(dir_of "$1")"
}
run_kosgd2() {
  local task phase
  for task in kosgd2_full kosgd2_actions_only; do
    kosgd2_action "$task" preflight >/dev/null || return $?
  done
  for task in kosgd2_full kosgd2_actions_only; do kosgd2_stage "$task" dev || return $?; done
  for phase in threshold question-threshold variant-threshold; do
    for task in kosgd2_full kosgd2_actions_only; do kosgd2_threshold "$task" "$phase" || return $?; done
  done
  for task in kosgd2_full kosgd2_actions_only; do kosgd2_stage "$task" test || return $?; done
  for task in kosgd2_full kosgd2_actions_only; do finish "$task" || return $?; done
  for task in kosgd2_full kosgd2_actions_only; do
    step local question-risk --run-dir "$(dir_of "$task")" &&
      step local score-variants risk --run-dir "$(dir_of "$task")" || return $?
  done
}
