"""명령 모듈의 검증 및 쓰기 경계."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_run
from tests.run.cli_support import Harness, output_files, put_yaml


@pytest.mark.parametrize("failure", ["no_seal", "test_incomplete", "extra_missing", "extra_partial"])
def test_score_requires_seal_and_all_stage_ids(tmp_path, monkeypatch, failure):
    h = Harness(tmp_path, "fc_call_decision")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    if failure != "extra_missing":
        h.run("extra")
    if failure == "no_seal":
        (h.directory / "test/seal.json").unlink()
    elif failure == "test_incomplete":
        (h.directory / "test/final.jsonl").write_text("")
    elif failure == "extra_partial":
        (h.directory / "extra/final.jsonl").write_text("")
    before = output_files(h.directory)
    assert h.command("score") == 1
    assert output_files(h.directory) == before


def test_late_score_failure_preserves_existing_outputs(h, monkeypatch):
    h.finish()
    from jeveval.run import cmd_score
    monkeypatch.setattr(cmd_score, "summary_from_risk", lambda **kw: (_ for _ in ()).throw(ValueError()))
    before = output_files(h.directory)
    assert h.command("score") == 1
    assert output_files(h.directory) == before



def test_provenance_mismatch_prevents_all_outputs(h):
    from jeveval.run import cmd_score
    h.finish()
    run_files.write_json(h.directory / "test/derived.json", {"derived_from": "wrong"})
    before = output_files(h.directory)
    with pytest.raises(ValueError, match="^derived provenance mismatch$"):
        cmd_score.run(root=h.root, run_dir=h.directory)
    assert output_files(h.directory) == before


def test_nonprimary_existing_summary_is_rejected_before_writes(tmp_path, monkeypatch):
    from jeveval.run import cmd_score
    h = Harness(tmp_path, "kosgd", "full")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.finish()
    h.variant = "actions_only"
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    run_files.write_json(h.directory / "summary.json", {"stale": True})
    before = output_files(h.directory)
    with pytest.raises(ValueError, match="^nonprimary summary already exists$"):
        cmd_score.run(root=h.root, run_dir=h.directory)
    assert output_files(h.directory) == before


def test_all_outputs_validated_before_ordered_writes(h, monkeypatch):
    from jeveval.run import cmd_score
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    checked, written = [], []
    encode, write = run_files.json_bytes, run_files.write_json
    def checked_bytes(value):
        checked.append(value)
        return encode(value)
    def tracked_write(path, value):
        assert len(checked) >= 3
        assert any(candidate is value for candidate in checked)
        write(path, value)
        assert path.is_file()
        written.append(path.name)
    monkeypatch.setattr(run_files, "json_bytes", checked_bytes)
    monkeypatch.setattr(run_files, "write_json", tracked_write)
    assert cmd_score.run(root=h.root, run_dir=h.directory)["ok"]
    assert written == ["risk.json", "scores.json", "summary.json"]
