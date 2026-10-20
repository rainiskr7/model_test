#!/bin/bash
# Bash 3.2; BASE assembly and aggregation live in the stdlib Python helpers.
smoke_main() {
  local root python
  root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || return 77
  python="$root/.venv/bin/python"
  [ -x "$python" ] || { echo 'INCONCLUSIVE: .venv/bin/python unavailable' >&2; return 77; }
  PYTHONPATH="$root" PYTHONDONTWRITEBYTECODE=1 "$python" -B -m orchestration.smoke.main "$@"
}

smoke_one() {
  local track=$1 model=${2:-}
  [ "$#" -ge 2 ] || { echo "usage: smoke_$track.sh <model_conf> [--out path]" >&2; return 2; }
  shift 2
  smoke_main "$model" "$track" "$@"
}
