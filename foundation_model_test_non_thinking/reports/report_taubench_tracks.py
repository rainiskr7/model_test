#!/usr/bin/env python3
"""Report only taubench results the contract admits, and refuse the rest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

from shared.taubench.scoring.report import collect, render_markdown


def _strict_status(summaries, unreadable) -> int:
    """거부와 읽기 실패를 순서대로 stderr에 진단하고 strict 종료 코드를 반환한다."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    # 호출 cwd와 관계없이 기본 산출물 기준은 <N>이다.
    parser.add_argument(
        "--base", type=Path, default=BASE,
        help="산출물을 읽을 기준 디렉터리(<PATH>/results, 기본값: 이 저장소); 채점 코드는 실행 중인 저장소의 패키지를 쓴다",
    )
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

    # taubench 가 reports/report_agent_tracks.py 에서 분리되면서 그쪽 --strict 의 CI 검사도
    # 함께 사라졌다. 거부된 런이 조용히 통과하면 게이트를 만든 의미가 없다.
    if args.strict:
        return _strict_status(summaries, unreadable)
    return 0


if __name__ == "__main__":
    sys.exit(main())
