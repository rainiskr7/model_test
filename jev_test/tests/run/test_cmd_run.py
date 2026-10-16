"""명령 모듈의 검증 및 쓰기 경계."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_run
from tests.run.cli_support import Harness, output_files, put_yaml


@pytest.mark.parametrize("failure", ["auth", "missing", "measurer", "items"])
@pytest.mark.parametrize("stage", ["dev", "test"])
def test_run_failure_before_any_write(h, monkeypatch, failure, stage):
    if stage == "test":
        h.run("dev")
        assert h.command("threshold") == 0
    sent = len(h.sent)
    if failure == "auth":
        monkeypatch.delenv("JEV_TEST_KEY")
    elif failure == "missing":
        path = h.root / h.args["model"]
        import yaml
        cfg = yaml.safe_load(path.read_text())
        cfg["served_name"] = None
        put_yaml(path, cfg)
    elif failure == "measurer":
        monkeypatch.setattr(cmd_run, "measurer_for", lambda cfg: (_ for _ in ()).throw(ValueError("secret")))
    else:
        monkeypatch.setattr(cmd_run.stage_inputs, "load_items", lambda **kw: (_ for _ in ()).throw(ValueError("secret")))
    before = output_files(h.root)
    with pytest.raises(ValueError):
        if failure == "measurer":
            cmd_run.run(**h.args, stage=stage, post=h.post)
        else:
            h.run(stage)
    assert output_files(h.root) == before and len(h.sent) == sent



def test_check_config_missing_fields_never_sends_or_writes(h, monkeypatch):
    from jeveval.io.config import read_yaml
    path = h.root / h.args["model"]
    config = read_yaml(path)
    config["served_name"] = None
    put_yaml(path, config)
    before = output_files(h.root)
    result = h.run("dev", check_config=True)
    assert result["ok"] is False and "served_name" in result["missing_for_run"]
    assert h.sent == [] and output_files(h.root) == before


@pytest.mark.parametrize("set_name", ["klue_mrc_answerable", "kosgd", "fc_call_decision"])
def test_extra_stage_only_functionchat(tmp_path, set_name):
    h = Harness(tmp_path, set_name, "full" if set_name == "kosgd" else "default")
    before = output_files(h.root)
    if set_name == "fc_call_decision":
        assert h.run("extra", check_config=True)["ok"] is True
    else:
        with pytest.raises(ValueError, match="^extra only supported for FunctionChat$"):
            h.run("extra", check_config=True)
    assert output_files(h.root) == before and h.sent == []


@pytest.mark.parametrize("secret", [None, "", "bad\nkey", "bad\x7fkey"])
def test_authentication_rejected_before_writes(h, monkeypatch, secret):
    if secret is None:
        monkeypatch.delenv("JEV_TEST_KEY")
    else:
        monkeypatch.setenv("JEV_TEST_KEY", secret)
    before = output_files(h.root)
    with pytest.raises(ValueError, match="^authentication unavailable$"):
        h.run("dev")
    assert output_files(h.root) == before and h.sent == []


def test_separate_actions_only_uses_derived_writer_without_auth(tmp_path, monkeypatch):
    h = Harness(tmp_path, "kosgd", "full")
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.run("dev")
    sent, source = len(h.sent), output_files(h.directory)
    h.variant = "actions_only"
    monkeypatch.delenv("JEV_TEST_KEY")
    calls, original = [], cmd_run.derived_stage.write_derived_stage
    def write(directory, stage, finals, provenance):
        calls.append((directory, stage, provenance))
        return original(directory, stage, finals, provenance)
    monkeypatch.setattr(cmd_run.derived_stage, "write_derived_stage", write)
    result = h.run("dev")
    assert result["derived"] is True and len(h.sent) == sent
    provenance = (h.directory.parent / "full").relative_to(h.root).as_posix()
    assert calls == [(h.directory, "dev", provenance)]
    assert run_files.read_json(h.directory / "dev/derived.json") == {"derived_from": provenance}
    assert output_files(h.directory.parent / "full") == source
