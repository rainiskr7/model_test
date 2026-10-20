"""Check judging completion independently of publication eligibility."""

import argparse
import json
import sys
from pathlib import Path


def valid_score(score) -> bool:
    """Accept exactly the judge's integer 0..10 score contract."""
    return not isinstance(score, bool) and isinstance(score, int) and 0 <= score <= 10


def check(results, summary) -> tuple[bool, str]:
    """Validate counts and every judged row without modifying either artifact."""
    if not isinstance(results, list) or not isinstance(summary, dict):
        return False, "results must be a list and summary must be an object"
    total, scored = summary.get("total"), summary.get("scored")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (total, scored)):
        return False, "total and scored must be integers"
    if not total == scored == len(results) > 0:
        return False, f"scored {scored}/{total}, rows={len(results)}"
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            return False, f"row {index} must be an object"
        if row.get("error"):
            return False, f"row {index} has a judge error"
        if not valid_score(row.get("score")):
            return False, f"row {index} score must be an integer from 0 through 10"
    return True, ""


def completion_rc(results, summary) -> int:
    """Report an incomplete judgment without exposing row contents."""
    ok, reason = check(results, summary)
    if not ok:
        print(f"[koffvqa_judge] incomplete: {reason}", file=sys.stderr)
        return 10
    return 0


def main(argv=None) -> int:
    """Read saved judge artifacts; distinguish unreadable input from incompletion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("judge_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        results = json.loads((args.judge_dir / "results.json").read_text(encoding="utf-8"))
        summary = json.loads((args.judge_dir / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"[koffvqa_judge] cannot read judge artifacts: {type(exc).__name__}", file=sys.stderr)
        return 2
    return completion_rc(results, summary)


if __name__ == "__main__":
    raise SystemExit(main())
