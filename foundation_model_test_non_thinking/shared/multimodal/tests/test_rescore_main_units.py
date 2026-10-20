"""입력: 합성 CLI 인자·격리 자식 프로세스. 출력: stdout·rc·무부작용 검증."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shared.multimodal.rescore.__main__ import main
from shared.multimodal.rescore.sessions import rescore_source
from shared.multimodal.tests.test_rescore_mtvqa_lmms_units import mtvqa_case
from shared.multimodal.tests.test_rescore_sessions_units import session_case


def test_cli_dry_run_and_external_output(tmp_path, monkeypatch, capsys):
    source, directory = session_case(tmp_path)
    monkeypatch.setattr("shared.multimodal.rescore.__main__.rescore_source",
                        lambda p: rescore_source(p, directory))
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["--base", str(tmp_path), "--bench", "k_mmbench"]) == 0
    dry_run = capsys.readouterr().out
    assert json.loads(dry_run)["sessions"][0]["accepted"] is True
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    output = tmp_path / "report.json"
    assert main(["--source", str(source), "--out", str(output)]) == 0
    assert output.read_text() == capsys.readouterr().out == dry_run


def test_cli_refuses_protected_path_before_scoring(tmp_path, monkeypatch, capsys):
    source, _ = session_case(tmp_path)
    monkeypatch.setattr("shared.multimodal.rescore.__main__.rescore_source",
                        lambda p: pytest.fail("must reject before scoring"))
    assert main(["--source", str(source), "--out", str(source / "out.json")]) == 2
    assert not (source / "out.json").exists()
    assert "rejected" in capsys.readouterr().err


def test_cli_reports_multiple_sources_and_corrupt_session_without_raw_text(tmp_path, monkeypatch, capsys):
    source, directory = session_case(tmp_path)
    monkeypatch.setattr("shared.multimodal.rescore.__main__.rescore_source",
                        lambda p: rescore_source(p, directory))
    corrupt = tmp_path / "bad/k_mmbench"
    corrupt.mkdir(parents=True)
    (corrupt / "results.json").write_text("SECRET_SENTINEL invalid json")
    assert main(["--source", str(source), "--source", str(corrupt)]) == 2
    text = capsys.readouterr().out
    assert "SECRET_SENTINEL" not in text
    assert [r["accepted"] for r in json.loads(text)["sessions"]] == [True, False]


def test_cli_rejects_incomplete_at_session_level(tmp_path, monkeypatch, capsys):
    source, directory = session_case(tmp_path)
    rows = json.loads((source / "results.json").read_text())
    (source / "results.json").write_text(json.dumps(rows[1:]))
    monkeypatch.setattr("shared.multimodal.rescore.__main__.rescore_source",
                        lambda p: rescore_source(p, directory))
    assert main(["--source", str(source)]) == 2
    assert json.loads(capsys.readouterr().out)["sessions"][0]["accuracy"] is None


def test_cli_rejects_multigold_at_session_level(tmp_path, monkeypatch, capsys):
    source, directory = session_case(tmp_path)
    source = source.with_name("mtvqa_kr")
    source.mkdir()
    rows, manifest = mtvqa_case()
    rows[0]["gold"] = ["서울", "부산"]
    (source / "results.json").write_text(json.dumps(rows))
    (source / "summary.json").write_text(json.dumps({"run_config": {"dataset": {
        "revision": manifest["revision"], "huggingface_id": manifest["dataset"]}}}))
    (directory / f'mtvqa_kr_{manifest["revision"]}.json').write_text(json.dumps(manifest))
    monkeypatch.setattr("shared.multimodal.rescore.__main__.rescore_source",
                        lambda p: rescore_source(p, directory))
    assert main(["--source", str(source)]) == 2
    value = json.loads(capsys.readouterr().out)["sessions"][0]
    assert value["accuracy"] is None
    assert value["issues"][0]["reason"] == "singleton_string_gold_required"


def test_module_entry_and_imports_do_not_change_environment_or_write(tmp_path):
    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    code = """
import importlib, os, socket
before = dict(os.environ)
def blocked(*a, **k):
    raise AssertionError('network forbidden')
socket.socket.connect = blocked
for name in ('manifest', 'sessions', 'kmmbench_circular', 'mtvqa_lmms', '__main__'):
    importlib.import_module('shared.multimodal.rescore.' + name)
assert dict(os.environ) == before
"""
    outcome = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path, env=env, capture_output=True)
    assert outcome.returncode == 0, outcome.stderr.decode()
    outcome = subprocess.run([sys.executable, "-B", "-m", "shared.multimodal.rescore",
                              "--base", str(tmp_path)], cwd=tmp_path, env=env, capture_output=True)
    assert outcome.returncode == 2 and b"rejected" in outcome.stderr
    assert not list(tmp_path.iterdir())
