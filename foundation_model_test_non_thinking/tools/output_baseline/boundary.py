"""Marker-based write boundary (does not detect write-and-restore)."""

import subprocess
from pathlib import Path

from tools.output_baseline.snapshot import git


def start(base, evidence):
    status = git(base, "status", "--short", "--", "results/").decode()
    marker = evidence / "write_boundary.marker"
    marker.touch()
    return {"marker": str(marker), "results_status_before": status}


def finish(base, record):
    found = subprocess.run(["find", "results", "data", "configs", "-newer", record["marker"]],
                           cwd=base, capture_output=True, text=True)
    status = git(base, "status", "--short", "--", "results/").decode()
    record.update(find_rc=found.returncode, newer_paths=found.stdout.splitlines(),
                  find_stderr=found.stderr, results_status_after=status)
    record["ok"] = found.returncode == 0 and not record["newer_paths"] and status == record["results_status_before"]
    return record["ok"]


def safe_output(base, path):
    resolved = Path(path).resolve()
    if any(resolved.is_relative_to((base / name).resolve()) for name in ("results", "data", "configs")):
        raise ValueError(f"output must be outside results/data/configs: {path}")
    return resolved
