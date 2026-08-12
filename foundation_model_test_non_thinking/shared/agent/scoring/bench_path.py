"""Locate the vendored Ko-AgentBench package for scoring."""

import os
import sys
from pathlib import Path


def ensure_bench_path() -> Path:
    """Add ``<MODEL_TEST_BASE>/data/Ko-AgentBench`` to sys.path.

    The scoring code imports the vendored ``bench`` package but never modifies
    it. MODEL_TEST_BASE must point at the class tree root.
    """
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError(
            "MODEL_TEST_BASE is required to locate data/Ko-AgentBench for agent scoring"
        )

    koa_dir = Path(base).resolve() / "data" / "Ko-AgentBench"
    if not (koa_dir / "bench" / "runner" / "metrics.py").is_file():
        raise RuntimeError(
            f"Ko-AgentBench metrics.py not found under {koa_dir}. "
            "Run shared/agent/install.sh or set MODEL_TEST_BASE correctly."
        )

    koa_str = str(koa_dir)
    if koa_str not in sys.path:
        sys.path.insert(0, koa_str)
    return koa_dir
