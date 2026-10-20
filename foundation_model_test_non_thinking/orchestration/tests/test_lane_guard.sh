#!/bin/bash
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec /bin/bash "$HERE/test_lane_guard_isolated.sh" "${1:-${LANEGUARD_TARGET:-$HERE/../lane_guard.sh}}"
