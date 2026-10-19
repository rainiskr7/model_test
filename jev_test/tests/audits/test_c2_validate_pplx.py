"""C2 감사: 질문 수와 요청 수를 구별하고 원문을 출력하지 않는다."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

from jeveval.io import records
from jeveval.run import context


def test_current_validator_counts_requests_and_choice_answers(audit_h, audit_module, capsys):
    h = audit_h
    h.run("dev")
    path = h.directory / "dev/attempts.jsonl"
    rows, _ = records.read_attempts(path)
    body = json.loads(rows[0].response_raw)
    for answer in body["answers"].values():
        answer["confidence"] = .5
    path.write_bytes(records.record_line(replace(rows[0], response_raw=json.dumps(body))))
    ctx = context.configuration(h.root, h.args["model"], h.args["task"])
    result = audit_module("c2_validate_pplx")["stage_summary"](ctx, h.directory, "dev")
    assert result["n_requests"] == result["n_choice_requests"] == result["n_choice_requests_warned"] == 1
    assert result["n_choice_answers"] == result["n_choice_in_range"] == 2
    assert result["reasons"] == {"valid": 1} and result["warnings"]["confidence_differs"] == 1
    assert not capsys.readouterr().out
    assert all(marker not in json.dumps(result) for marker in h.markers.values())


def test_isolated_cli_hides_exception_input(tmp_path):
    script = Path(__file__).resolve().parents[2] / "audits/replay_20261019/c2_validate_pplx.py"
    result = subprocess.run([sys.executable, "-I", str(script), "private-state-canary", "r"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1 and not result.stderr
    assert "private-state-canary" not in result.stdout
    assert json.loads(result.stdout)["ok"] is False
