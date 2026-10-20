#!/usr/bin/env python3
"""입력: 결과 base·세션 범위. 출력: 기존 발행 보고서와 검증된 참고 부록 Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

from shared.multimodal.publish.report import collect, render_markdown, strict_failed
from shared.multimodal.rescore.report_inputs import ConfigError, build_appendix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base", type=Path, default=BASE,
        help="산출물을 읽을 기준 디렉터리(<PATH>/results, 기본값: 이 저장소); 채점 코드는 실행 중인 저장소의 패키지를 쓴다",
    )
    parser.add_argument("--run", help="scope report/strict validation to one session")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-markdown", type=Path)
    parser.add_argument("--no-official", action="store_true", help="참고 부록의 YAML 읽기·재채점 생략")
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
    if not args.no_official:
        try:
            markdown = markdown + "\n" + build_appendix(args.base, sidecars, comparison_sidecars)
        except ConfigError as exc:
            print(f"report configuration rejected: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"official appendix failed: {type(exc).__name__}", file=sys.stderr)
            return 2
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
