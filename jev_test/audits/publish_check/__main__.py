"""무엇: 공개 전 검사 CLI. 입력: root/base/head/out·제한. 출력: 외부 JSON·수량 요약·실패 종료."""

import argparse
from pathlib import Path
import sys

from .git_objects import git
from .report import output_path, write
from .scan import scan


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reader-based publication text check")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="jev_test source root")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--length", type=int, default=12)
    parser.add_argument("--max-blob-bytes", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--max-candidates", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    try:
        repo = Path(git(args.root, "rev-parse", "--show-toplevel").decode().strip())
        out = output_path(repo, args.out)
        result = scan(args.root, args.base, args.head, length=args.length, max_bytes=args.max_blob_bytes,
                      max_candidates=args.max_candidates, scratch=out.parent)
        write(out, result)
    except Exception:
        print("publish_check failed; no publication approval", file=sys.stderr)
        return 2
    print(f"blobs={result['counts']['total_blobs']} checked={result['counts']['checked_blobs']} "
          f"failed={result['counts']['failed_blobs']} matches={result['counts']['match_intervals']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
