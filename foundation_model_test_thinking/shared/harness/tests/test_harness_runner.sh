#!/bin/bash
# C1-C5; accepts an old runner or .new. Scratch/fixtures stay in .codex_work.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$HERE/runner_checks.py" harness "${1:-${HARNESS_TARGET:-$HERE/../run_harness.sh.new}}"
