"""Validate one agent-track result directory.

The CLI reads only ``summary.json`` and direct ``L1.json`` ... ``L7.json``
children of the selected agent results directory. It never inspects other tracks.

Exit codes:
    0  Results are valid (warnings are allowed).
    1  Results are invalid because validation errors were found.
    2  Invocation, configuration, input-reading, or unexpected internal error.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__:
    from . import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from .aggregate import (
        ALL_LEVELS,
        SCORABLE_LEVELS,
        V4_EXCLUDED_LEVELS,
        V4_HEADLINE_LEVELS,
        safe_model_name,
        results_model_dir_name,
    )
    from .validate_rules import (
        _check_scoring_version,
        _check_by_level,
        _check_cache_miss_warnings,
        _check_l7_record_only,
        _load_raw_levels,
        _check_l2_single_candidate_warning,
        _check_raw_metadata_consistency,
        _check_headline_v2,
        _check_scoring_v3,
        _check_scoring_v4,
        _load_json,
    )
    from .level_spec import JUDGE_METRICS, LEVEL_SPECS, LEVEL_SPECS_V3
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from __init__ import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from aggregate import (
        ALL_LEVELS,
        SCORABLE_LEVELS,
        V4_EXCLUDED_LEVELS,
        V4_HEADLINE_LEVELS,
        safe_model_name,
        results_model_dir_name,
    )
    from validate_rules import (
        _check_scoring_version,
        _check_by_level,
        _check_cache_miss_warnings,
        _check_l7_record_only,
        _load_raw_levels,
        _check_l2_single_candidate_warning,
        _check_raw_metadata_consistency,
        _check_headline_v2,
        _check_scoring_v3,
        _check_scoring_v4,
        _load_json,
    )
    from level_spec import JUDGE_METRICS, LEVEL_SPECS, LEVEL_SPECS_V3


PREFIX = "[agent-validate]"
EXIT_CODE_HELP = """exit codes:
  0  results valid (warnings allowed)
  1  results invalid -- validation errors found
  2  invocation, configuration, input-reading, or internal error"""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _results_dir_from_args(args) -> Path:
    if args.results_dir is not None:
        if not args.results_dir:
            raise RuntimeError("--results-dir must not be empty")
        if args.model is not None or args.timestamp is not None or args.track is not None:
            raise RuntimeError(
                "--results-dir cannot be combined with --model, --timestamp, or --track"
            )
        return Path(args.results_dir).resolve()
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError("MODEL_TEST_BASE is required without --results-dir")
    if not args.model or not args.timestamp:
        raise RuntimeError("--model and --timestamp are required without --results-dir")
    return (
        Path(base).resolve()
        / "results"
        / results_model_dir_name(Path(base), args.model)
        / args.timestamp
        / "language"
        / (args.track or "agent")
    )


def _preflight_results_dir(results_dir: Path) -> None:
    if not results_dir.exists():
        raise RuntimeError(f"results directory does not exist: {results_dir}")
    if not results_dir.is_dir():
        raise RuntimeError(f"results path is not a directory: {results_dir}")

    summary_path = results_dir / "summary.json"
    if not summary_path.exists():
        return

    direct_json = [summary_path]
    direct_json.extend(results_dir / f"{level}.json" for level in ALL_LEVELS)
    for path in direct_json:
        if path.exists():
            try:
                _load_json(path)
            except Exception as exc:
                raise RuntimeError(
                    f"{path.name} could not be read or parsed: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc


def validate_summary(
    summary: Dict[str, Any], results_dir: Path
) -> Tuple[List[str], List[str]]:
    """Validate an in-memory summary against one agent results directory."""
    results_dir = Path(results_dir)
    failures: List[str] = []
    warnings: List[str] = []
    _check_scoring_version(summary, failures, warnings)
    _check_by_level(summary, failures, warnings)
    by_level = summary.get("by_level")
    by_level = by_level if isinstance(by_level, dict) else {}
    _check_cache_miss_warnings(summary, by_level, failures, warnings)
    _check_l7_record_only(by_level, failures, warnings)
    raw_levels = _load_raw_levels(results_dir, failures, warnings)
    _check_l2_single_candidate_warning(by_level, raw_levels, failures, warnings)
    _check_raw_metadata_consistency(summary, by_level, raw_levels, results_dir, failures, warnings)
    _check_headline_v2(summary, by_level, failures, warnings)
    _check_scoring_v3(summary, failures, warnings)
    _check_scoring_v4(summary, failures, warnings)
    return failures, warnings


def validate_results_dir(results_dir: Path) -> Tuple[List[str], List[str]]:
    """Load and validate exactly one agent results directory."""

    results_dir = Path(results_dir)
    warnings: List[str] = []
    summary_path = results_dir / "summary.json"
    if not summary_path.is_file():
        return ([f"summary.json not found: {summary_path}"], warnings)
    try:
        summary = _load_json(summary_path)
    except Exception as exc:
        return (
            [f"summary.json could not be parsed: {type(exc).__name__}: {exc}"],
            warnings,
        )
    return validate_summary(summary, results_dir)


def parse_args(argv=None):
    parser = _ArgumentParser(
        description=__doc__,
        epilog=EXIT_CODE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--results-dir", help="Path to language/<agent-track>")
    parser.add_argument("--model", help="Model name used to build results path")
    parser.add_argument("--timestamp", help="Evaluation timestamp used to build results path")
    parser.add_argument("--track", help="Agent track folder under language/ (default: agent)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        results_dir = _results_dir_from_args(parse_args(argv))
        _preflight_results_dir(results_dir)
        failures, warnings = validate_results_dir(results_dir)
    except Exception as exc:
        print(f"{PREFIX} ERROR {type(exc).__name__}: {exc}")
        return 2
    for warning in warnings:
        print(f"{PREFIX} WARN {warning}")
    if failures:
        for failure in failures:
            print(f"{PREFIX} FAIL {failure}")
        print(f"{PREFIX} FAILED {results_dir} ({len(failures)} error(s))")
        return 1
    print(f"{PREFIX} PASS {results_dir} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
