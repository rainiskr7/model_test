#!/usr/bin/env python3
"""Derive multimodal publication sidecars; dry-run unless --write is given."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.multimodal.publish.derive import derive_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true", help="write sidecars below _derived")
    args = parser.parse_args(argv)
    try:
        derived = derive_all(args.base, write=args.write)
    except Exception as exc:
        print(f"derive failed: {exc}", file=sys.stderr)
        return 2
    if not derived:
        print("multimodal 산출물이 없습니다.", file=sys.stderr)
        return 2
    action = "wrote" if args.write else "would write"
    for path, sidecar in derived:
        counts = sidecar.get("counts") or {}
        status = sidecar["status"]
        status_text = status.value if hasattr(status, "value") else status
        print(
            f"{action} {path}: {status_text} "
            f"(attempted={counts.get('attempted')}, errored={counts.get('errored')}, "
            f"unresolved={counts.get('unresolved')})"
        )
    print(f"{len(derived)} sidecar(s); {'write complete' if args.write else 'dry-run'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
