"""Shared scoring paths and runner timestamps."""

import os
from datetime import datetime
from pathlib import Path

from shared.resultspath.model_dir import results_model_dir_name


def scoring_results_dir(args, base_default: Path) -> Path:
    if args.results_dir:
        return args.results_dir.resolve()
    base = Path(os.environ.get("MODEL_TEST_BASE") or base_default)
    timestamp = args.timestamp or os.environ.get("EVAL_TIMESTAMP")
    if not args.model or not timestamp:
        raise ValueError("--model and --timestamp (or EVAL_TIMESTAMP) are required")
    return (
        base / "results" / results_model_dir_name(base, args.model)
        / timestamp / "language" / args.track
    )


def run_timestamp(base_dir: Path) -> str:
    value = os.environ.get("EVAL_TIMESTAMP")
    if value:
        return value
    session_file = base_dir / ".eval_session"
    if session_file.is_file():
        value = session_file.read_text(encoding="utf-8").strip()
    return value or datetime.now().strftime("%Y%m%d_%H%M%S")
