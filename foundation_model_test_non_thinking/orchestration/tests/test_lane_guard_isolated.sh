#!/bin/bash
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BASE=$(cd "$HERE/../.." && pwd)
PYTHONPATH="$BASE" PYTHONDONTWRITEBYTECODE=1 python3 -m orchestration.tests.lane_guard_check "$@"
