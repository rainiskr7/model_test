"""무엇: T0 fixture 생성 CLI · 입력: root/합성 template · 출력: 공개 행 참조 fixture · 계약 §8-7 T-c."""

import argparse
from collections import Counter
from pathlib import Path

from jeveval.data.t0_fixture import make_fixture
from jeveval.io.run_files import read_json
from jeveval.io.t0_files import write_fixture
from jeveval.io.t0_sources import read_sources


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build out-of-pool T0 fixture")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--template", default="configs/t0/template_v1.json")
    parser.add_argument("--out", default="configs/t0/fixture_v1.json")
    args = parser.parse_args(argv)
    fixture = make_fixture(read_sources(args.root), read_json(args.root / args.template))
    write_fixture(args.root / args.out, fixture)
    counts = Counter(c["state_ref"]["set"] for c in fixture["cases"] if "state_ref" in c)
    print(dict(cases=len(fixture["cases"]), sources=dict(sorted(counts.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
