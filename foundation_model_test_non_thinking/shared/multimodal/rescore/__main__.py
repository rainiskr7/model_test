"""입력: rescore CLI 인자. 출력: 세션별 JSON(stdout/외부 파일)과 rc 0 또는 2."""

import argparse
import json
from pathlib import Path
import sys

from shared.multimodal.rescore.sessions import (
    BENCHES, discover_sources, rescore_source, validate_output, write_output,
)


def main(argv=None):
    """CLI를 해석하고 세션 읽기·채점·선택적 출력 쓰기를 조립한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, action="append")
    parser.add_argument("--bench", choices=BENCHES)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    sources = args.source if args.source else discover_sources(
        args.base, (args.bench,) if args.bench else BENCHES)
    try:
        if args.out:
            validate_output(args.out, args.base, sources)
        if not sources:
            raise ValueError("no sources")
        results = []
        for source in sources:
            try:
                if source.name not in BENCHES or (args.bench and source.name != args.bench):
                    raise ValueError("benchmark mismatch")
                results.append(rescore_source(source))
            except (OSError, ValueError, KeyError, TypeError):
                results.append({"source": source.as_posix(), "accepted": False,
                                "issues": [{"reason": "invalid_session_or_manifest"}]})
        report = {"schema_version": 1, "sessions": results}
        if args.out:
            write_output(args.out, report, args.base, sources)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0 if all(r["accepted"] for r in results) else 2
    except (OSError, ValueError):
        print("rescore rejected: no sources or invalid output path", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
