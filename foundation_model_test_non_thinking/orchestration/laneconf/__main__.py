"""Emit validated shell assignments without exporting lane settings."""
import argparse
import shlex
import sys

from orchestration.laneconf import ConfigError, parse, resolve
from orchestration.laneconf.files import read_text, read_tracks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracks-dir", required=True)
    parser.add_argument("model_conf", help="path to models/<name>.conf")
    parser.add_argument("track")
    args = parser.parse_args()
    try:
        values = resolve(parse(read_text(args.model_conf)), args.track, read_tracks(args.tracks_dir))
    except ConfigError as exc:
        print(f"run_lane: {exc}", file=sys.stderr)
        return 2
    # Produce no partial output on errors; only whitelisted variable names reach eval.
    sys.stdout.write("".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
