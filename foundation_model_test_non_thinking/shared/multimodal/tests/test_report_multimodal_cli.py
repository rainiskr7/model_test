"""Exercise the report CLI using only temporary publication fixtures."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from shared.multimodal.publish.report import render_markdown
from shared.multimodal.tests.test_publish_select_report import sidecar


CLI = Path(__file__).resolve().parents[3] / "reports/report_multimodal_tracks.py"


def run_cli(base, *args):
    return subprocess.run(
        [sys.executable, str(CLI), "--base", str(base), *map(str, args)],
        text=True, capture_output=True, check=False,
    )


def test_empty_base_preserves_cli_output(tmp_path):
    result = run_cli(tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "multimodal 산출물이 없습니다.\n"


def test_write_markdown_creates_report_for_requested_run(tmp_path):
    source = "results/model/session/vision/multimodal/k_dtcbench"
    derived = tmp_path / source / "_derived"
    derived.mkdir(parents=True)
    raw = b'[{"response": "A", "answer": "A"}]\n'
    (derived.parent / "results.json").write_bytes(raw)
    config = tmp_path / "configs/model_identity.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"model": "model"}), encoding="utf-8")
    record = sidecar(
        "session", "2026-01-01T00:00:00+00:00",
        source=source, benchmark="K-DTCBench", canonical_model="model",
        artifact_sha="sha256:" + hashlib.sha256(raw).hexdigest(),
    )
    (derived / "publish.json").write_text(json.dumps(record), encoding="utf-8")
    # A different session without a sidecar must be excluded by --run.
    (tmp_path / "results/model/other/vision/multimodal/k_dtcbench").mkdir(parents=True)
    output = tmp_path / "report.md"
    result = run_cli(tmp_path, "--run", "session", "--write-markdown", output)
    assert result.returncode == 0
    assert result.stdout == f"wrote {output}\n"
    assert result.stderr == ""
    expected, _ = render_markdown([record], [])
    assert output.read_text(encoding="utf-8") == expected
    assert "K-DTCBench" in expected
    assert "100.00%" in expected


def test_strict_requires_run(tmp_path):
    result = run_cli(tmp_path, "--strict")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "usage: report_multimodal_tracks.py [-h] [--base BASE] [--run RUN] [--strict]\n"
        "                                   [--write-markdown WRITE_MARKDOWN]\n"
        "report_multimodal_tracks.py: error: --strict requires --run\n"
    )
