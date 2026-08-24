#!/usr/bin/env python3
"""Report only multimodal results admitted by the publication contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.multimodal.publish.report import collect, render_markdown, strict_failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("."))
    parser.add_argument("--run", help="scope report/strict validation to one session")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-markdown", type=Path)
    args = parser.parse_args(argv)
    if args.strict and not args.run:
        parser.error("--strict requires --run")
    sidecars, missing = collect(args.base, args.run)
    if not sidecars and not missing:
        print("multimodal 산출물이 없습니다.", file=sys.stderr)
        return 2
    comparison_sidecars = None
    if args.strict:
        comparison_sidecars, _ = collect(args.base)
    markdown, ambiguous = render_markdown(sidecars, missing, comparison_sidecars)
    if args.write_markdown:
        args.write_markdown.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.write_markdown}")
    else:
        print(markdown, end="")
    if args.strict and strict_failed(sidecars, missing, ambiguous, comparison_sidecars):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
