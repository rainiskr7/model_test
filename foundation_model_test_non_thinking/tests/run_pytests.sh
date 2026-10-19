#!/bin/bash
# Usage: run_pytests.sh [track] [pytest options...]; no track means all tests.
set -u
BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || exit 2
cd "$BASE" || exit 2
target=
case "${1:-}" in
  ''|-*) ;;
  agent|functionchat|taubench|multimodal|nlu|harness|jsonwrite|publish|resultspath)
    target="shared/$1"; shift ;;
  configs|reports|orchestration) target=$1; shift ;;
  baseline) target=tools/output_baseline; shift ;;
  *) printf 'Unknown test track: %s\n' "$1" >&2; exit 2 ;;
esac
if [ -n "$target" ]; then
  [ -d "$target" ] || { printf 'Test track directory unavailable: %s\n' "$target" >&2; exit 2; }
  set -- "$BASE/$target" "$@"
fi
exec "$BASE/.venv/bin/python" -m pytest -c "$BASE/pytest.ini" --rootdir "$BASE" "$@"
