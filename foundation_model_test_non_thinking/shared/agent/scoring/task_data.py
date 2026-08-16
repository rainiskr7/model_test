"""SHA-checked benchmark task-data joins used only by scoring v3."""

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple


PINNED_BENCHMARK_SHA = "1174fedd9fa1c7177baa0cbff039a765c9b14d02"
L6_TASK_FILE = Path("bench/tasks/L6.json")


def _benchmark_dir() -> Path:
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError(
            "MODEL_TEST_BASE is required for the SHA-checked L6 golden_fields join"
        )
    return Path(base).resolve() / "data" / "Ko-AgentBench"


def _git_output(benchmark_dir: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(benchmark_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise RuntimeError(f"could not verify Ko-AgentBench checkout: {detail.strip()}") from exc
    return completed.stdout.strip()


def _load_pinned_l6_tasks() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    benchmark_dir = _benchmark_dir()
    actual_sha = _git_output(benchmark_dir, "rev-parse", "HEAD")
    if actual_sha != PINNED_BENCHMARK_SHA:
        raise RuntimeError(
            "Ko-AgentBench SHA mismatch for L6 join: "
            f"expected {PINNED_BENCHMARK_SHA}, got {actual_sha}"
        )

    dirty = _git_output(
        benchmark_dir, "status", "--porcelain", "--", str(L6_TASK_FILE)
    )
    if dirty:
        raise RuntimeError(
            f"Ko-AgentBench task file is modified at pinned SHA: {L6_TASK_FILE}"
        )

    task_path = benchmark_dir / L6_TASK_FILE
    try:
        raw_bytes = task_path.read_bytes()
        task_list = json.loads(raw_bytes)
    except Exception as exc:
        raise RuntimeError(
            f"could not read pinned L6 task file {task_path}: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(task_list, list):
        raise RuntimeError("pinned L6 task file must contain a JSON list")

    by_id: Dict[str, Dict[str, Any]] = {}
    for task in task_list:
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not task_id:
            raise RuntimeError("pinned L6 task file contains an entry with missing task_id")
        if task_id in by_id:
            raise RuntimeError(f"duplicate task_id in pinned L6 task file: {task_id}")
        by_id[task_id] = task

    provenance = {
        "golden_fields_source": "sha_checked_task_file_join",
        "join_needed": True,
        "benchmark_sha": actual_sha,
        "task_file": str(L6_TASK_FILE),
        "task_file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }
    return by_id, provenance


def prepare_v3_loaded(
    loaded: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Copy loaded results and fill only absent L6 ``golden_fields`` values."""
    prepared = dict(loaded)
    l6_data = loaded.get("L6")
    if not isinstance(l6_data, dict):
        return prepared, {
            "golden_fields_source": "not_applicable_no_l6",
            "join_needed": False,
            "benchmark_sha": PINNED_BENCHMARK_SHA,
            "task_file": None,
            "task_file_sha256": None,
            "tasks_joined": 0,
        }

    tasks_key = "results" if isinstance(l6_data.get("results"), list) else "tasks"
    tasks = l6_data.get(tasks_key)
    if not isinstance(tasks, list):
        tasks = []
    missing = [
        task
        for task in tasks
        if not isinstance(task, dict) or "golden_fields" not in task
    ]
    if not missing:
        return prepared, {
            "golden_fields_source": "artifact",
            "join_needed": False,
            "benchmark_sha": PINNED_BENCHMARK_SHA,
            "task_file": None,
            "task_file_sha256": None,
            "tasks_joined": 0,
        }

    seen_task_ids = set()
    for task in tasks:
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not task_id:
            raise RuntimeError("L6 result missing task_id required for golden_fields join")
        if task_id in seen_task_ids:
            raise RuntimeError(f"duplicate task_id in L6 results: {task_id}")
        seen_task_ids.add(task_id)

    task_data, provenance = _load_pinned_l6_tasks()
    l6_copy = copy.deepcopy(l6_data)
    joined = 0
    for task in l6_copy.get(tasks_key, []):
        if "golden_fields" in task:
            continue
        task_id = task.get("task_id")
        if not task_id:
            raise RuntimeError("L6 result missing task_id required for golden_fields join")
        if task_id not in task_data:
            raise RuntimeError(f"L6 task_id not found in pinned task file: {task_id}")
        task["golden_fields"] = copy.deepcopy(task_data[task_id].get("golden_fields", []))
        joined += 1
    prepared["L6"] = l6_copy
    provenance["tasks_joined"] = joined
    return prepared, provenance
