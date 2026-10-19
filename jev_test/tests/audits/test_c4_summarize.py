"""C4 감사: ID 값은 출력하지 않고 집합 차이 수와 상태/경고만 낸다."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

from jeveval.io import records


def test_ids_warnings_and_hidden_record_strings(audit_h, audit_module):
    h = audit_h
    h.run("dev")
    source = h.directory / "dev/final.jsonl"
    current = source.with_name("new.jsonl")
    row = records.read_finals(source)[0][0]
    current.write_bytes(records.record_line(replace(row, warnings=["confidence_differs", "private-state-canary"])))
    report = audit_module("c4_summarize")["summary"](current, source)
    assert report["ids_equal"] and report["by_status"] == {"ok": 1}
    assert report["warnings"] == {"confidence_differs": 1, "unknown": 1}
    assert "private-state-canary" not in json.dumps(report)
    current.write_bytes(records.record_line(replace(row, logical_id="private-state-canary")))
    report = audit_module("c4_summarize")["summary"](current, source)
    assert report["n_missing"] == report["n_unexpected"] == 1 and not report["ids_equal"]


def test_isolated_cli_reports_only_summary(audit_h):
    h = audit_h
    h.finish()
    root = h.directory.parents[2]
    script = Path(__file__).resolve().parents[2] / "audits/replay_20261019/c4_summarize.py"
    result = subprocess.run([sys.executable, "-I", str(script), str(root), str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["ok"] and not result.stderr
    assert all(marker not in result.stdout for marker in h.markers.values())
