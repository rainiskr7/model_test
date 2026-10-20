"""CLI for the approved R8 serving smoke; no production lane is started."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from orchestration.laneconf import ConfigError
from orchestration.smoke.cleanup import finish
from orchestration.smoke.configuration import TRACKS, configuration
from orchestration.smoke.execution import run
from orchestration.smoke.isolation import assemble, environment, outside


def execute_smoke(root, args):
    """Own one BASE, including configuration failures and interrupted execution."""
    base = None
    try:
        base = assemble(root)
        stamp = datetime.now(timezone.utc).strftime("smoke_%Y%m%d_%H%M%S_%f")
        ctx = configuration(root, base, environment(root, base, stamp), stamp, args.model_conf)
        summary = run(ctx, list(dict.fromkeys(args.tracks or TRACKS)))
    except ConfigError as exc:
        summary = dict(rc=2, reason=str(exc))
    except KeyboardInterrupt:
        summary = dict(rc=130, status="INCONCLUSIVE", reason="interrupted", base=str(base) if base else None)
    except Exception as exc:
        summary = dict(rc=77, status="INCONCLUSIVE", reason=str(exc), base=str(base) if base else None)
    # No track ran on ConfigError, even --keep has no diagnostic artifacts to retain.
    return finish(summary, root, base, keep=args.keep and summary['rc'] != 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_conf")
    parser.add_argument("tracks", nargs="*")
    parser.add_argument("--out", type=Path, help="summary JSON outside the code root")
    parser.add_argument("--keep", action="store_true", help="retain BASE even after PASS")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_]+", args.model_conf) or any(t not in TRACKS for t in args.tracks):
        parser.error("invalid model_conf or track")
    root = Path(__file__).resolve().parents[2]
    try:
        output = outside(args.out, root) if args.out else None
        summary = execute_smoke(root, args)
    except Exception as exc:
        summary = dict(rc=77, status="INCONCLUSIVE", reason=str(exc),
                       base=None, base_kept=False)
    if summary['rc'] == 2:
        print(f"smoke: {summary['reason']}", file=sys.stderr)
        if 'cleanup_error' in summary:
            print(f"smoke: cleanup failed: {summary['cleanup_error']}", file=sys.stderr)
        return 2
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.out and 'output' in locals() and output:
        output.write_text(text)
    sys.stdout.write(text)
    return summary["rc"]


if __name__ == "__main__":
    raise SystemExit(main())
