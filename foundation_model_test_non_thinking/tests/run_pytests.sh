#!/bin/bash
# Usage: run_pytests.sh [track] [pytest options...]; no track means all tests.
#        run_pytests.sh --list
set -u
BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || exit 2
cd "$BASE" || exit 2

# Static discovery only: listing must not import tests or invoke pytest.
shared_track() {
  [[ "$1" =~ ^[a-z0-9_]+$ ]] && [ -d "shared/$1" ] || return 1
  [ -n "$(find "shared/$1/" -type f \( -name 'test_*.py' -o -name '*_test.py' \) -print)" ]
}

list_tracks() {
  local name directory
  for name in configs reports orchestration baseline; do
    directory=$name
    [ "$name" != baseline ] || directory=tools/output_baseline
    [ ! -d "$directory" ] || printf '%s\n' "$name"
  done
  for directory in shared/*; do
    name=${directory##*/}
    # Aliases own these names even if a same-named shared directory appears.
    case "$name" in configs|reports|orchestration|baseline) continue ;; esac
    if shared_track "$name"; then printf '%s\n' "$name"; fi
  done
}

if [ "${1:-}" = --list ]; then
  [ "$#" -eq 1 ] || { printf '%s\n' 'Usage: run_pytests.sh --list' >&2; exit 2; }
  list_tracks | LC_ALL=C sort -u
  exit $?
fi

target=
case "${1:-}" in
  ''|-*) ;;
  configs|reports|orchestration) target=$1; shift ;;
  baseline) target=tools/output_baseline; shift ;;
  *)
    shared_track "$1" || { printf 'Unknown test track: %s\n' "$1" >&2; exit 2; }
    target="shared/$1"; shift ;;
esac
if [ -n "$target" ]; then
  [ -d "$target" ] || { printf 'Test track directory unavailable: %s\n' "$target" >&2; exit 2; }
  set -- "$BASE/$target" "$@"
fi
exec "$BASE/.venv/bin/python" -m pytest -c "$BASE/pytest.ini" --rootdir "$BASE" "$@"
