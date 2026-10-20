"""입력: 모델 A/B 폴더·벤치·bootstrap 인자. 출력: stdout Markdown/JSON 비교 또는 rc 2."""

import argparse
import json
from pathlib import Path
import sys

from shared.stats.item_scores import METRICS
from shared.stats.paired import bootstrap
from shared.stats.selection import SelectionError, check_comparison, load_cohort


def comparison(a, b, seed=0, resamples=2000):
    """선택된 코호트를 검사하고 bootstrap 결과와 재현 근거를 조립한다."""
    check_comparison(a, b)
    return {"schema_version": 1, "metric": a["metric"], "metric_version": a["version"],
            "upstream": a["upstream"], "cohort": a["cohort"],
            "a": {k: a[k] for k in ("model", "runs", "folded_duplicates")},
            "b": {k: b[k] for k in ("model", "runs", "folded_duplicates")},
            **bootstrap(a, b, seed, resamples)}


def render_json(value):
    """비교 객체를 안정된 JSON 문자열로 반환한다."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def render_markdown(value):
    """비교 객체를 퍼센트·퍼센트포인트 단위의 Markdown 표로 반환한다."""
    def cell(text):
        return str(text).replace("|", "\\|").replace("\n", " ")

    low, high = value["ci95"]
    lines = [f'지표: `{value["metric"]}` · 차이 = A−B (pp)',
             "", "| A | B | A (%) | B (%) | 차이 (pp) | 95% 구간 (pp) | 문항 / 이미지 | 반복 A / B |",
             "|---|---|---:|---:|---:|---:|---:|---:|",
             f'| {cell(value["a"]["model"])} | {cell(value["b"]["model"])} | '
             f'{100 * value["mean_a"]:.4f} | {100 * value["mean_b"]:.4f} | '
             f'{100 * value["difference"]:+.4f} | [{100 * low:+.4f}, {100 * high:+.4f}] | '
             f'{value["items"]} / {value["images"]} | '
             f'{value["repetitions_a"]} / {value["repetitions_b"]} |', "",
             value["interpretation"] + " (반복 간 변동 미포함).",
             f'seed={value["seed"]}, resamples={value["resamples"]}; {value["method"]}.',
             f'코호트: `{value["cohort"][2]}`']
    if value["upstream"]:
        upstream = value["upstream"]
        lines.append(f'upstream: {upstream["repository"]}/blob/{upstream["commit"]}/{upstream["path"]}')
    for label in ("a", "b"):
        lines.extend(["", f'{label.upper()} 반복:'] + [f'- `{v["source"]}`' for v in value[label]["runs"]])
    return "\n".join(lines) + "\n"


def main(argv=None):
    """CLI를 실행하며 파일 쓰기 없이 결과 또는 안전한 후보 오류를 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--bench", choices=METRICS, required=True)
    parser.add_argument("--cohort", help="양쪽에 적용할 정확한 protocol fingerprint")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        if args.resamples < 1:
            raise SelectionError("positive resamples required")
        a = load_cohort(args.base, args.a, args.bench, args.cohort)
        b = load_cohort(args.base, args.b, args.bench, args.cohort)
        value = comparison(a, b, args.seed, args.resamples)
        print((render_json if args.format == "json" else render_markdown)(value), end="")
        return 0
    except SelectionError as exc:
        print(render_json({"error": str(exc), "candidates": exc.candidates}), end="", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print('{"error": "invalid comparison input", "candidates": []}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
