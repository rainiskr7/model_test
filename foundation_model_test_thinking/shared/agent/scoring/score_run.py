"""CLI for deterministic Ko-AgentBench agent scoring."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

if __package__:
    from .aggregate import ALL_LEVELS, build_summary_from_loaded, safe_model_name
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from aggregate import ALL_LEVELS, build_summary_from_loaded, safe_model_name


PREFIX = "[agent-scoring]"


def _fmt(value: Optional[float]) -> str:
    return "null" if value is None else f"{value:.3f}"


def _metric_token(name: str, entry: Dict[str, Any]) -> str:
    token = f"{name}={_fmt(entry.get('score'))}/{entry.get('status')}"
    if entry.get("status") in ("partial", "error"):
        token += f"({entry.get('n_scored')}/{entry.get('n_tasks')})"
    return token


def _result_dir_from_args(args) -> Path:
    if args.results_dir:
        return Path(args.results_dir).resolve()
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError("--results-dir or MODEL_TEST_BASE is required")
    if not args.model or not args.timestamp:
        raise RuntimeError("--model and --timestamp are required without --results-dir")
    return (
        Path(base).resolve()
        / "results"
        / safe_model_name(args.model)
        / args.timestamp
        / "language"
        / args.track
    )


def _load_level(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_summary(results_dir: Path) -> Dict[str, Any]:
    if not results_dir.is_dir():
        raise RuntimeError(f"results dir not found: {results_dir}")

    loaded = {}
    for level in ALL_LEVELS:
        path = results_dir / f"{level}.json"
        if path.is_file():
            loaded[level] = _load_level(path)

    return build_summary_from_loaded(loaded, results_dir)


def print_table(summary: Dict[str, Any], skipped_count: int) -> None:
    print(f"{PREFIX} model={summary['model']} track={summary['track']}")
    for level in ALL_LEVELS:
        result = summary["by_level"].get(level)
        if not result:
            continue
        metrics = " ".join(
            _metric_token(name, entry)
            for name, entry in result["metrics"].items()
            if entry.get("in_score") or name == "FSM_prefix"
        )
        unscorable = ""
        if result.get("score") is None and result.get("unscorable_reason"):
            unscorable = f" unscorable={result['unscorable_reason']}"
        print(
            f"{PREFIX} {level} total={result['total']} "
            f"score={_fmt(result.get('score'))}{unscorable} {metrics}"
        )
    scored_levels = summary.get(
        "scored_levels",
        sum(
            result.get("score") is not None
            for result in summary.get("by_level", {}).values()
        ),
    )
    required_levels = summary.get("required_levels", len(ALL_LEVELS) - 1)
    print(
        f"{PREFIX} agent_score={_fmt(summary.get('agent_score'))} "
        f"status={summary.get('agent_score_status', 'unknown')} "
        f"scored_levels={scored_levels}/{required_levels}"
    )
    print(f"{PREFIX} skipped_missing_levels={skipped_count}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", help="Path to language/<track> containing L*.json")
    parser.add_argument("--model", help="Model name used to build results path")
    parser.add_argument("--timestamp", help="Evaluation timestamp used to build results path")
    parser.add_argument("--track", default="agent", help="Track folder under language/")
    parser.add_argument("--dry-run", action="store_true", help="Do not write summary.json")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        results_dir = _result_dir_from_args(args)
        summary = build_summary(results_dir)
        skipped = len(summary["levels_missing"])
        print_table(summary, skipped)
        if not args.dry_run:
            out = results_dir / "summary.json"
            with out.open("w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"{PREFIX} wrote {out}")
        return 0
    except Exception as exc:
        print(f"{PREFIX} error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
