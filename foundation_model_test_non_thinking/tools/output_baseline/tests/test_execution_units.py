import os
import sys

from tools.output_baseline.execution import command, environment


def test_environment_isolated_without_mutating_parent(tmp_path):
    before = dict(os.environ)
    env = environment(tmp_path / "head", tmp_path / "actual")
    assert env["PYTHONPATH"] == str(tmp_path / "head")
    assert env["MODEL_TEST_BASE"] == str(tmp_path / "actual")
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert dict(os.environ) == before


def test_subprocess_evidence_retains_full_stdout_stderr_and_rc(tmp_path):
    record = command([sys.executable, "-B", "-c",
                      "import sys; print('full stdout'); print('error', file=sys.stderr); sys.exit(3)"],
                     tmp_path, tmp_path, tmp_path / "logs")
    assert record["rc"] == 3
    assert (tmp_path / "logs/stdout").read_bytes() == b"full stdout\n"
    assert (tmp_path / "logs/stderr").read_bytes() == b"error\n"
    assert record["elapsed_seconds"] >= 0
