"""CLI for the approved R8 serving smoke; no production lane is started."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from .configuration import TRACKS, configuration
from .execution import run
from .isolation import assemble, environment, outside


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_conf")
    parser.add_argument("tracks", nargs="*")
    parser.add_argument("--out", type=Path, help="summary JSON outside the code root; detailed logs stay in B")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_]+", args.model_conf) or any(t not in TRACKS for t in args.tracks):
        parser.error("invalid model_conf or track")
    root = Path(__file__).resolve().parents[2]
    try:
        output = outside(args.out, root) if args.out else None
        base = assemble(root)
        stamp = datetime.now(timezone.utc).strftime("smoke_%Y%m%d_%H%M%S_%f")
        ctx = configuration(root, base, environment(root, base, stamp), stamp, args.model_conf)
        summary = run(ctx, list(dict.fromkeys(args.tracks or TRACKS)))
    except Exception as exc:
        summary = dict(rc=77, status="INCONCLUSIVE", reason=str(exc),
                       base=str(base) if 'base' in locals() else None)
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.out and 'output' in locals() and output:
        output.write_text(text)
    sys.stdout.write(text)
    return summary["rc"]


if __name__ == "__main__":
    raise SystemExit(main())
