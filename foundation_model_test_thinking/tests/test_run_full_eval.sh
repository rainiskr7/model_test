#!/bin/bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$HERE/../shared/harness/tests/runner_checks.py" full "${1:-${FULL_EVAL_TARGET:-$HERE/../run_full_eval.sh}}"
