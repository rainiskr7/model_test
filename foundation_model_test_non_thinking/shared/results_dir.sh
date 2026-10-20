#!/bin/bash
# §12 예외: 동결 harness가 이 helper를 단독 복사해 쓰므로 heredoc 유지.
# Print the sole existing casefold-equivalent spelling under <base>/results.
# Sourcing defines the helper only; no directories or session files are written.
results_model_dir() {
  python3 - "$1" "$2" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "results"
requested = sys.argv[2]
matches = sorted(p.name for p in root.iterdir()
                 if p.is_dir() and p.name.casefold() == requested.casefold()) if root.is_dir() else []
if len(matches) > 1:
    print(f"case-fold ambiguous results model directory for {requested!r}: {matches}", file=sys.stderr)
    sys.exit(2)
print(matches[0] if matches else requested)
PY
}
