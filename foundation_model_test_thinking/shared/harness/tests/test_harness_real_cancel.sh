#!/bin/bash
# Loopback only, offline datasets/tokenizers. Return 77 means INCONCLUSIVE.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${HARNESS_TARGET:-$HERE/../run_harness.sh.new}}"
shift "$(( $# > 0 ? 1 : 0 ))"
exec python3 -I "$HERE/runner_checks.py" real "$TARGET" "$@"
