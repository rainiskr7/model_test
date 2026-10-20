#!/bin/bash
# Real runner modules, synthetic credential/server; never contacts a serving HOST.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd) || exit 77
PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1 "$ROOT/.venv/bin/python" -B -m orchestration.smoke.offline_checks
