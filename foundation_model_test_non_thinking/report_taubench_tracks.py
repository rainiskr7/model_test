#!/usr/bin/env python3
"""Report only taubench results the contract admits, and refuse the rest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.taubench.scoring.report import collect, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("."))
    parser.add_argument("--write-markdown", type=Path)
    args = parser.parse_args(argv)

    summaries, unreadable = collect(args.base)
    if not summaries and not unreadable:
        print("taubench 산출물이 없습니다.", file=sys.stderr)
        return 2
    markdown = render_markdown(summaries, unreadable)
    if args.write_markdown:
        args.write_markdown.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.write_markdown}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
