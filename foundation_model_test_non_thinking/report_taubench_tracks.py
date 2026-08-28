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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="게이트가 거부한 런이나 읽을 수 없는 산출물이 있으면 exit 1 (CI)",
    )
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

    # taubench 가 report_agent_tracks.py 에서 분리되면서 그쪽 --strict 의 CI 검사도
    # 함께 사라졌다. 거부된 런이 조용히 통과하면 게이트를 만든 의미가 없다.
    if args.strict:
        rejected = [
            summary
            for summary in summaries
            if (summary.get("publish_status") or {}).get("publishable") is False
        ]
        for summary in rejected:
            failures = (summary.get("publish_status") or {}).get("failures") or []
            print(
                f"[taubench/report] REJECTED: {summary.get('model')} / "
                f"{summary.get('_session')} — {'; '.join(map(str, failures))}",
                file=sys.stderr,
            )
        for item in unreadable:
            print(f"[taubench/report] UNREADABLE: {item['path']} — {item['reason']}", file=sys.stderr)
        if rejected or unreadable:
            print(
                f"[taubench/report] NOT CLEAN: 거부 {len(rejected)}건, "
                f"읽기 실패 {len(unreadable)}건",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
