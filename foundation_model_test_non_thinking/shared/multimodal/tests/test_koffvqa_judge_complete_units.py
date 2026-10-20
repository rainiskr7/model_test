"""Completion is an execution contract, independent of the publication gate."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shared.multimodal.benches.koffvqa_judge_complete import check

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("rows,summary,ok", [
    ([{"score": 0}, {"score": 10, "error": None}], {"total": 2, "scored": 2}, True),
    ([{"score": 8}, {"score": None, "error": "failed"}], {"total": 2, "scored": 1}, False),
    ([{"score": None, "error": "failed"}], {"total": 1, "scored": 0}, False),
    ([], {"total": 0, "scored": 0}, False),
    ([{"score": 8}], {"total": 2, "scored": 1}, False),
    ([{"score": 8}, {"score": 9}], {"total": 1, "scored": 1}, False),
    ([{"score": 8, "error": "failed"}], {"total": 1, "scored": 1}, False),
    ([{"score": 8}], {"total": True, "scored": 1}, False),
    ([{"score": 8}], {"total": 1, "scored": 1.0}, False),
    ([{"score": 8}], {}, False),
    ({}, {"total": 1, "scored": 1}, False),
    ([{"score": 8}], [], False),
    ([None], {"total": 1, "scored": 1}, False),
])
def test_counts_rows_and_shape_are_checked_without_mutation(rows, summary, ok):
    original = copy.deepcopy((rows, summary))
    accepted, reason = check(rows, summary)
    assert accepted is ok
    assert bool(reason) is not ok
    assert (rows, summary) == original


@pytest.mark.parametrize("score", [True, False, -1, 11, 5.0, "5", None])
def test_invalid_scores(score):
    assert check([{"score": score}], {"total": 1, "scored": 1})[0] is False


@pytest.mark.parametrize("case,rc", [
    ("complete", 0), ("partial", 10), ("shape", 10), ("missing", 2),
    ("broken", 2), ("encoding", 2), ("directory", 2),
])
def test_cli_return_codes_and_read_only_artifacts(tmp_path, case, rc):
    if case != "missing":
        rows = [{"score": 8}] if case == "complete" else [{"score": None, "error": "private row text"}]
        (tmp_path / "results.json").write_text(json.dumps({} if case == "shape" else rows))
        summary = tmp_path / "summary.json"
        summary.write_text('{"total": 1, "scored": 1}')
        if case == "broken":
            summary.write_text("private broken JSON")
        elif case == "encoding":
            summary.write_bytes(b"\xff")
        elif case == "directory":
            summary.unlink()
            summary.mkdir()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result = subprocess.run(
        [sys.executable, "-B", "-m", "shared.multimodal.benches.koffvqa_judge_complete", str(tmp_path)],
        cwd=tmp_path, env={"PATH": os.defpath, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == rc
    assert result.stdout == ""
    assert "private" not in result.stderr
    assert ("[koffvqa_judge] incomplete:" in result.stderr) is (rc == 10)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
