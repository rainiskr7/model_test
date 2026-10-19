#!/bin/bash
set -u
BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || exit 1
cd "$BASE" || exit 1
failed=0
# 운영 레인 실행 중 금지: test_lane_guard.sh (guard 실프로세스 시험).
# test_lane_guard_isolated.sh는 위 래퍼가 호출하므로 중복 실행하지 않는다.
for script in \
  orchestration/tests/test_lane_guard.sh \
  orchestration/tests/test_run_lane_equivalence.sh \
  orchestration/tests/test_run_lane_full.sh \
  orchestration/tests/test_smoke_offline.sh \
  tests/test_run_full_eval.sh \
  shared/harness/tests/test_harness_runner.sh
do
  set -- "$script"
  if [ "$script" = shared/harness/tests/test_harness_runner.sh ]; then
    set -- "$@" shared/harness/run_harness.sh
  fi
  /bin/bash "$@"
  rc=$?
  printf 'SHELL_TEST %s rc=%s\n' "$script" "$rc"
  [ "$rc" -eq 0 ] || failed=1
done
# INCONCLUSIVE(rc 77)도 전체 성공으로 합치지 않는다.
exit "$failed"
