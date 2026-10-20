#!/bin/bash
# Usage: run_smoke.sh <model_conf> [track ...] [--keep] [--out /tmp/summary.json]
set -u
source "$(dirname "$0")/smoke_lib.sh"
smoke_main "$@"
