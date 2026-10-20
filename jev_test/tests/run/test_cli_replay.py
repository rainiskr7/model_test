"""무엇: 복사→offline→재개 CLI 통합 · 입력: 합성 서버 기록 · 출력: 바이트/집합/봉인 · 계약 §5-5c."""

import json

import pytest

from jeveval.io import archive, records, run_files
from jeveval.run import cli, cmd_run, context
from jeveval.run.layout import run_dir
from jeveval.run.seal import check_seal
from tests.run.cli_support import Harness
from tests.run.file_support import output_files
from tests.run.replay_support import mixed_source


def command(h, name, stage, **options):
    argv = [name, "--model", h.args["model"], "--task", h.args["task"], "--stage", stage, "--run-id", "r2"]
    for key, value in options.items():
        argv.append("--" + key.replace("_", "-"))
        if value is not True:
            argv.append(str(value))
    return cli.main(argv)


def result(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_systemone_copy_offline_byte_identity_and_archive(h, monkeypatch, capsys):
    h.finish()
    before, sent = output_files(h.directory), len(h.sent)
    monkeypatch.setattr(cmd_run, "measurer_for", lambda cfg: h)
    monkeypatch.delenv("JEV_TEST_KEY")
    target = run_dir(h.root / "results", "synthetic", "r2", h.set, h.variant)
    for stage in ("dev", "test"):
        assert command(h, "replay", stage, source_run_dir=h.directory) == 0
        assert command(h, "run", stage, offline=True) == 0
        summary = result(capsys)
        assert summary["n_sent"] == summary["n_deferred"] == 0
        assert (target / stage / "final.jsonl").read_bytes() == before[f"{stage}/final.jsonl"]
        if stage == "dev":
            assert cli.main(["threshold", "--run-dir", str(target)]) == 0
    assert cli.main(["score", "--run-dir", str(target)]) == 0
    assert cli.main(["certify", "--run-dir", str(target)]) == 0
    assert cli.main(["archive", "--run-id", "r2"]) == 0
    manifest = run_files.read_json(target / "archive.json")
    assert archive.verify_archive(h.root / manifest["archive"], manifest) == []
    assert sum(p.endswith("/replay.json") for p in manifest["files"]) == 2
    assert output_files(h.directory) == before and len(h.sent) == sent


def test_test_copy_without_threshold_and_offline_url_conflict(h, monkeypatch):
    h.finish()
    monkeypatch.setattr(cmd_run, "measurer_for", lambda cfg: h)
    assert command(h, "replay", "test", source_run_dir=h.directory) == 0
    before = output_files(h.root)
    assert command(h, "run", "test", offline=True) == 1
    assert command(h, "run", "dev", offline=True, base_url="http://localhost:1") == 1
    assert output_files(h.root) == before


def test_mixed_offline_replay_then_online_resume(tmp_path, monkeypatch, capsys):
    h = Harness(tmp_path, "fc_call_decision", kind="b1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "private-test-key")
    expected = mixed_source(h, monkeypatch)
    before, sent = output_files(h.directory), len(h.sent)
    monkeypatch.setattr(cmd_run, "measurer_for", lambda cfg: h)
    monkeypatch.setattr(cmd_run.http, "post", h.post)
    target = run_dir(h.root / "results", "synthetic", "r2", h.set, h.variant)
    for stage in ("dev", "test"):
        assert command(h, "replay", stage, source_run_dir=h.directory) == 0
        snapshot = output_files(target)
        assert command(h, "replay", stage, source_run_dir=h.directory) == 0
        assert output_files(target) == snapshot
        assert command(h, "run", stage, offline=True) == 0
        summary = result(capsys)
        assert summary["n_sent"] == 0 and summary["n_deferred"] == (3 if stage == "test" else 0)
        if stage == "dev":
            assert cli.main(["threshold", "--run-dir", str(target)]) == 0
    assert len(h.sent) == sent and check_seal(target) == []
    assert len(records.read_finals(target / "test/final.jsonl")[0]) == 2
    snapshot = output_files(target)
    assert command(h, "replay", "test", source_run_dir=h.directory) == 1
    assert output_files(target) == snapshot  # 계획 §1-5: final 존재 시 C6보다 보수적으로 거부.
    assert cli.main(["score", "--run-dir", str(target)]) == 1
    assert command(h, "run", "test", base_url="http://localhost:1") == 0
    summary = result(capsys)
    assert summary["n_sent"] == 4 and summary["n_deferred"] == 0 and len(h.sent) - sent == 4
    finals, _ = records.read_finals(target / "test/final.jsonl")
    attempts, _ = records.read_attempts(target / "test/attempts.jsonl")
    assert {f.logical_id for f in finals} == expected and check_seal(target) == []
    assert max(a.attempt for a in attempts) == 2
    assert sorted(a.attempt for a in attempts if ":retry:" in a.logical_id) == [1, 1, 2]
    assert output_files(h.directory) == before
    assert len(context.stage(context.restore(h.root, target), "test").finals) == 5
