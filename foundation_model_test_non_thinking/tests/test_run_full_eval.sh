#!/bin/bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${FULL_EVAL_TARGET:-$HERE/../run_full_eval.sh}}"
python3 -I "$HERE/../shared/harness/tests/runner_checks.py" full "$TARGET"
legacy_rc=$?
python3 -I "$HERE/full_eval_timeout_checks.py" "$TARGET"
timeout_rc=$?
printf 'FULL_EVAL_TEST legacy_rc=%s timeout_rc=%s\n' "$legacy_rc" "$timeout_rc"
# Run both suites even if the first fails; preserve its failure (including rc 77).
[ "$legacy_rc" -eq 0 ] || exit "$legacy_rc"
exit "$timeout_rc"
