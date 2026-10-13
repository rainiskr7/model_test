#!/bin/bash
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec python3 -I "$HERE/../../shared/harness/tests/runner_checks.py" guard "${1:-${LANEGUARD_TARGET:-$HERE/../lane_guard.sh}}"
