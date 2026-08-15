"""Load immutable Ko-AgentBench task definitions for deterministic scoring."""

import hashlib
import json
import os
from typing import Dict, Iterable

try:
    from .bench_path import ensure_bench_path
except ImportError:  # direct file loading in tests
    from bench_path import ensure_bench_path


def _task_file(level: str):
    koa_dir = ensure_bench_path()
    path = koa_dir / "bench" / "tasks" / f"{level}.json"
    if not path.is_file():
        raise RuntimeError(f"Ko-AgentBench task file not found: {path}")
    return path


def load_bench_tasks(level: str) -> Dict[str, dict]:
    """Return a task_id -> task map from the vendored bench task file."""
    path = _task_file(level)
    with path.open("r", encoding="utf-8") as f:
        tasks = json.load(f)
    if not isinstance(tasks, list):
        raise RuntimeError(f"Ko-AgentBench task file must contain a list: {path}")

    task_map = {}
    for task in tasks:
        if not isinstance(task, dict) or not task.get("task_id"):
            raise RuntimeError(f"Ko-AgentBench task missing task_id in {path}")
        task_map[str(task["task_id"])] = task
    return task_map


def tasks_digest(level: str) -> str:
    """Return the sha256 digest of the vendored task file bytes."""
    return hashlib.sha256(_task_file(level).read_bytes()).hexdigest()


def _bench_code_digest(*parts: str):
    path = ensure_bench_path().joinpath(*parts)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bench_pin(levels: Iterable[str]) -> dict:
    pin = {
        "tasks_sha256": {level: tasks_digest(level) for level in levels},
        "metrics_sha256": _bench_code_digest("bench", "runner", "metrics.py"),
        "runner_sha256": _bench_code_digest("bench", "runner", "run.py"),
    }
    bench_sha = os.environ.get("KO_AGENTBENCH_SHA")
    if bench_sha:
        pin["ko_agentbench_sha"] = bench_sha
    return pin
