"""무엇: 명령 통합/실패 무변경 · 입력: 합성 파일 · 출력: 봉인/요약/누출 없음 · 계약 ⑥b R1–R7."""

import json
import os

import pytest

from jeveval.io import run_files
from jeveval.run import cli, cmd_run
from tests.run.cli_support import Harness, output_files, put_yaml




def test_canary_cli_pipeline_and_certify_mutations(h, monkeypatch, capsys):
    original = cmd_run.run
    monkeypatch.setattr(cmd_run, "run", lambda **kw: original(**kw, measurer=h, post=h.post))
    args = ["--model", h.args["model"], "--task", h.args["task"], "--run-id", "r1"]
    assert cli.main(["run", *args, "--stage", "dev"]) == 0
    assert h.command("threshold") == 0
    assert cli.main(["run", *args, "--stage", "test"]) == 0
    assert h.command("score") == h.command("certify") == 0
    cell = run_files.read_json(h.directory / "risk.json")["cells"]["0.02"]
    summary = run_files.read_json(h.directory / "summary.json")
    for key in ("status", "insufficient_by_design"):
        assert summary[key] == cell[key]
    for key in ("n_accepted", "k_errors", "U"):
        assert summary[key] == cell["test"][key]
    coverage = cell["test"]["coverage"]
    assert summary["coverage_observed"] == coverage
    assert summary["score_rule"] == "meets_only"
    assert summary["score"] == (coverage["num"] / coverage["den"]
        if cell["status"] == "MEETS" and coverage["den"] > 0 else 0.0)
    committed = ["fingerprint.json", "threshold.json", "test/seal.json", "scores.json", "risk.json", "summary.json"]
    for name in committed:
        raw = (h.directory / name).read_text()
        assert all(marker not in raw for marker in h.markers.values())
        assert "private-test-key" not in raw
    before = output_files(h.directory)
    assert h.command("score") == 0
    assert output_files(h.directory) == before
    threshold = h.directory / "threshold.json"
    value = run_files.read_json(threshold)
    value["by_tau"]["0.02"]["t_star"] = .8
    run_files.write_json(threshold, value)
    os.utime(threshold, (0, 0))
    assert h.command("certify") == 1
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["checks"] == {"a": True, "b": False, "c": False}
    threshold.write_bytes(before["threshold.json"])
    os.utime(threshold, (2_000_000_000, 2_000_000_000))
    assert h.command("certify") == 0
    assert "threshold_mtime_after_seal" in capsys.readouterr().out




def test_check_config_base_url_and_sanitized_errors(h, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("check-config must not measure or load data")
    monkeypatch.setattr(cmd_run, "measurer_for", forbidden)
    monkeypatch.setattr(cmd_run.stage_inputs, "load_items", forbidden)
    before = output_files(h.root)
    args = ["run", "--model", h.args["model"], "--task", h.args["task"],
            "--stage", "dev", "--run-id", "r1", "--check-config"]
    assert cli.main(args + ["--base-url", "http://127.0.0.1:9"]) == 0
    assert output_files(h.root) == before
    assert cli.main(args + ["--base-url", "SECRET_INVALID_URL"]) == 1
    assert "SECRET_INVALID_URL" not in capsys.readouterr().out




def test_functionchat_all_rows_and_threshold_stage_isolation(tmp_path, monkeypatch):
    h = Harness(tmp_path, "fc_call_decision")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.finish()
    populations = run_files.read_json(h.directory / "scores.json")["populations"]
    assert populations["test"]["counts"]["n_sampled"] == 1
    assert populations["test"]["certified"] is True
    assert populations["all_rows"]["counts"]["n_sampled"] == 3
    assert populations["all_rows"]["certified"] is False
    before = output_files(h.directory)
    assert h.command("threshold") == 1
    assert output_files(h.directory) == before


@pytest.mark.parametrize("command", ["threshold", "score", "certify"])
@pytest.mark.parametrize("changed", ["configs/datasets.yaml", "configs/tasks/klue_mrc_answerable.yaml"])
def test_frozen_input_changes_reject_all_consumers(h, command, changed):
    h.finish()
    path = h.root / changed
    path.write_text(path.read_text() + "\n# changed\n")
    before = output_files(h.directory)
    assert h.command(command) == 1
    assert output_files(h.directory) == before






def test_test_without_threshold_and_missing_check_config(h, capsys):
    import yaml
    h.run("dev")
    before = output_files(h.directory)
    with pytest.raises(ValueError):
        h.run("test")
    assert output_files(h.directory) == before
    path = h.root / h.args["model"]
    cfg = yaml.safe_load(path.read_text())
    cfg["base_url"] = None
    put_yaml(path, cfg)
    args = ["run", "--model", h.args["model"], "--task", h.args["task"],
            "--stage", "dev", "--run-id", "r1", "--check-config"]
    assert cli.main(args) == 1
    assert "base_url" in json.loads(capsys.readouterr().out.splitlines()[-1])["missing_for_run"]
    assert cli.main(args + ["--base-url", "http://127.0.0.1:9"]) == 0
